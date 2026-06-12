"""Google Earth Engine authentication & initialization (docs/STRUCTURE.md §8).

Two non-interactive auth paths, in priority order (DEC-011, DEC-012):

1. **Service account (preferred, headless).** If a service-account key is
   available (``EE_SERVICE_ACCOUNT_KEY`` env var, or the default
   ``secrets/*.json`` key), initialize from it. Fully non-interactive, so a clean
   checkout reproduces without a browser (S12) and the project is read from the
   key itself.
2. **Cached user credentials.** Falls back to whatever ``earthengine
   authenticate`` cached for this machine.

This module NEVER triggers the interactive flow and never re-auths inside a retry
loop (§9). Initialization is idempotent: repeated calls after the first success
are cheap no-ops.

Usage:
    from clients.gee_auth import initialize
    initialize()                      # service account if available, else cached creds
    initialize(project="my-gee-prj")  # override the billing project
"""

from __future__ import annotations

import glob
import json
import os

# The Cloud project that bills/serves Earth Engine requests. EE requires a
# project since the high-volume endpoints launched; read it from the env so it
# is never hard-coded.
_PROJECT_ENV_VAR = "EE_PROJECT"

# Path to a service-account JSON key. When set (or when a single key is found in
# secrets/), auth is fully non-interactive (DEC-012).
_KEY_ENV_VAR = "EE_SERVICE_ACCOUNT_KEY"

# Default discovery glob for a service-account key dropped into secrets/. The
# secrets/ dir is gitignored; a clean checkout sets EE_SERVICE_ACCOUNT_KEY or
# places the key here.
_SECRETS_KEY_GLOB = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "secrets", "*.json"
)

_AUTH_HINT = (
    "Earth Engine is not authenticated for this machine. Use EITHER:\n"
    "  (preferred, non-interactive) a service-account key —\n"
    "    set EE_SERVICE_ACCOUNT_KEY=<path-to-key.json>  (or drop it in secrets/)\n"
    "  (interactive, human-run ONCE) cached user credentials —\n"
    "    earthengine authenticate\n"
    "and set the billing project if not in the key (docs/STRUCTURE.md §8):\n"
    "    set EE_PROJECT=<your-gcloud-project>   # or pass project= to initialize()\n"
)

# Module-level latch so initialize() is idempotent and never re-auths in a loop.
_initialized = False


class GEEAuthError(RuntimeError):
    """Earth Engine could not be initialized from available credentials."""


def _find_service_account_key() -> str | None:
    """Locate a service-account key: env var first, then a lone secrets/ key.

    Returns the path to a JSON file whose ``type`` is ``service_account``, or
    ``None``. If secrets/ holds several JSONs, only a *single unambiguous*
    service-account key is auto-used; otherwise the caller must set
    ``EE_SERVICE_ACCOUNT_KEY`` explicitly.
    """
    explicit = os.environ.get(_KEY_ENV_VAR)
    if explicit:
        return explicit if os.path.isfile(explicit) else None

    candidates = []
    for path in glob.glob(_SECRETS_KEY_GLOB):
        try:
            with open(path, encoding="utf-8") as fh:
                if json.load(fh).get("type") == "service_account":
                    candidates.append(path)
        except (OSError, ValueError):
            continue
    return candidates[0] if len(candidates) == 1 else None


def initialize(project: str | None = None, *, force: bool = False) -> None:
    """Initialize Earth Engine non-interactively. Idempotent.

    Tries a service-account key first (DEC-012), then cached user credentials
    (DEC-011). Never launches the interactive auth flow.

    Parameters
    ----------
    project:
        Cloud project to bill EE requests to. Falls back to ``EE_PROJECT``, then
        to the ``project_id`` embedded in the service-account key, then to EE's
        own default.
    force:
        Re-run ``ee.Initialize`` even if this process already initialized once.
        Default ``False`` so retry loops are cheap no-ops (§9).

    Raises
    ------
    GEEAuthError
        If neither a service-account key nor cached credentials yield a working
        session (with an actionable hint). Never auths interactively here.
    """
    global _initialized
    if _initialized and not force:
        return

    try:
        import ee  # local import so importing this module doesn't require ee
    except ImportError as exc:  # pragma: no cover - env not yet built
        raise GEEAuthError(
            "earthengine-api is not installed; create the env first "
            "(conda env update -f environment.yml)."
        ) from exc

    project = project or os.environ.get(_PROJECT_ENV_VAR)
    key_path = _find_service_account_key()

    try:
        if key_path:
            with open(key_path, encoding="utf-8") as fh:
                key_info = json.load(fh)
            credentials = ee.ServiceAccountCredentials(
                key_info["client_email"], key_path
            )
            ee.Initialize(credentials, project=project or key_info.get("project_id"))
        elif project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except (ee.EEException, KeyError, OSError, ValueError) as exc:
        # Common cause: missing/expired credentials, or a malformed key. Surface
        # the non-interactive remedy rather than attempting to auth here.
        raise GEEAuthError(f"{_AUTH_HINT}\nUnderlying Earth Engine error: {exc}") from exc

    _initialized = True


def is_initialized() -> bool:
    """True if this process has successfully initialized Earth Engine."""
    return _initialized
