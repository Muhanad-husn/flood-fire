"""Google Earth Engine authentication & initialization (docs/STRUCTURE.md §8).

Auth is interactive and human-run ONCE: `earthengine authenticate`. This module
only initializes an already-authenticated session — it never triggers the
interactive flow, and never re-auths inside a retry loop (§9). Initialization is
idempotent: repeated calls after the first success are cheap no-ops.

Usage:
    from clients.gee_auth import initialize
    initialize()                      # uses EE_PROJECT env var if set
    initialize(project="my-gee-prj")  # or pass explicitly
"""

from __future__ import annotations

import os

# The Cloud project that bills/serves Earth Engine requests. EE requires a
# project since the high-volume endpoints launched; read it from the env so it
# is never hard-coded.
_PROJECT_ENV_VAR = "EE_PROJECT"

_AUTH_HINT = (
    "Earth Engine is not authenticated for this machine.\n"
    "Run the interactive flow ONCE (human, not an agent):\n"
    "    earthengine authenticate\n"
    "and set the billing project (docs/STRUCTURE.md §8):\n"
    "    export EE_PROJECT=<your-gcloud-project>   # or pass project= to initialize()\n"
)

# Module-level latch so initialize() is idempotent and never re-auths in a loop.
_initialized = False


class GEEAuthError(RuntimeError):
    """Earth Engine could not be initialized from cached credentials."""


def initialize(project: str | None = None, *, force: bool = False) -> None:
    """Initialize Earth Engine from cached credentials. Idempotent.

    Parameters
    ----------
    project:
        Cloud project to bill EE requests to. Falls back to the ``EE_PROJECT``
        env var, then to EE's own default if neither is set.
    force:
        Re-run ``ee.Initialize`` even if this process already initialized once.
        Default ``False`` so retry loops are cheap no-ops (§9).

    Raises
    ------
    GEEAuthError
        If no cached credentials exist (with an actionable ``earthengine
        authenticate`` hint) or initialization otherwise fails. This function
        NEVER launches the interactive auth flow itself.
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

    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except ee.EEException as exc:
        # The common cause is missing/expired cached credentials. Surface the
        # one-time interactive remedy rather than attempting to auth here.
        raise GEEAuthError(f"{_AUTH_HINT}\nUnderlying Earth Engine error: {exc}") from exc

    _initialized = True


def is_initialized() -> bool:
    """True if this process has successfully initialized Earth Engine."""
    return _initialized
