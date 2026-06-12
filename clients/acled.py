"""ACLED conflict-event client (docs/STRUCTURE.md §5).

ACLED moved to **OAuth2 via myACLED**; the legacy static "API key" query-string
flow is deprecated (DEC-013 / S2 handoff). This client does a password-grant
token exchange against ``/oauth/token``, caches the access (24 h) and refresh
(14 d) tokens in a gitignored state file, and refreshes silently — credentials
(``[acled].username`` / ``[acled].password`` in secrets.toml, or ``ACLED_EMAIL`` /
``ACLED_KEY`` env) are read once and **tokens are never written to secrets.toml**.

Events feed RQ2 (S10): overlay conflict events on validated VIIRS/dNBR fire
detections to test whether 2026 crop fires track conflict frontlines — a
proportionate, descriptive linkage (PRODUCT §9), never proof of cause.

Pulls are cached/checkpointed per page so a paged, interrupted query resumes
without re-pulling (§9). ACLED data is **proprietary** (attribution required,
redistribution restricted) — cache locally, cite, never republish raw.

    from clients.acled import fetch_events
    rows = fetch_events("2026-05-01", "2026-07-31", country="Syria")
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from clients._common import Cache, _CACHE_ROOT, secret

_TOKEN_URL = "https://acleddata.com/oauth/token"
_READ_URL = "https://acleddata.com/api/acled/read"
_CLIENT_ID = "acled"
_PAGE_SIZE = 500          # rows/page; ACLED paginates with ?page=N
_REFRESH_TTL_S = 14 * 86400  # refresh token ~14 days (access expiry comes from the API)
_EXPIRY_BUFFER_S = 60     # refresh a little early to avoid edge-of-expiry 401s

# ACLED admin1 strings for the canonical AOIs, confirmed against the live
# `admin1` field (distinct_admin1("Syria"), 2026-06-12). Optional spatial filter
# for S10 — note ACLED uses spaces, not the hyphens/transliterations elsewhere.
ACLED_ADMIN1 = {
    "deir_ez_zor": "Deir ez Zor",
    "raqqa": "Ar Raqqa",
    "hasakah": "Al Hasakeh",
    "latakia": "Lattakia",
}

_cache = Cache("acled")
_TOKEN_PATH = _CACHE_ROOT / "acled" / "_token.json"


class AcledError(RuntimeError):
    """ACLED auth or query failed."""


# --- token lifecycle ----------------------------------------------------------

def _creds() -> tuple[str, str]:
    user = secret("acled", "username", env="ACLED_EMAIL")
    pw = secret("acled", "password", env="ACLED_KEY")
    return user, pw


def _read_token_state() -> dict:
    if not _TOKEN_PATH.is_file():
        return {}
    try:
        import json

        return json.loads(_TOKEN_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_token_state(state: dict) -> None:
    import json

    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_PATH.write_text(json.dumps(state), encoding="utf-8")


def _store_tokens(resp_json: dict) -> dict:
    now = time.time()
    state = {
        "access_token": resp_json["access_token"],
        "refresh_token": resp_json.get("refresh_token"),
        "access_expires_at": now + int(resp_json.get("expires_in", 86400)) - _EXPIRY_BUFFER_S,
        "refresh_expires_at": now + _REFRESH_TTL_S - _EXPIRY_BUFFER_S,
    }
    _write_token_state(state)
    return state


def _password_grant() -> dict:
    user, pw = _creds()
    resp = requests.post(
        _TOKEN_URL,
        data={"username": user, "password": pw, "grant_type": "password", "client_id": _CLIENT_ID},
        timeout=60,
    )
    if not resp.ok:
        raise AcledError(f"ACLED password grant failed ({resp.status_code}): {resp.text[:200]}")
    return _store_tokens(resp.json())


def _refresh_grant(refresh_token: str) -> dict:
    resp = requests.post(
        _TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": _CLIENT_ID},
        timeout=60,
    )
    if not resp.ok:
        raise AcledError("refresh rejected")  # caller falls back to password grant
    return _store_tokens(resp.json())


def _access_token() -> str:
    """Return a valid bearer token, minting/refreshing as needed (cached, no re-auth loop)."""
    state = _read_token_state()
    now = time.time()
    if state.get("access_token") and now < state.get("access_expires_at", 0):
        return state["access_token"]
    # Access expired: try refresh, else password grant.
    if state.get("refresh_token") and now < state.get("refresh_expires_at", 0):
        try:
            return _refresh_grant(state["refresh_token"])["access_token"]
        except AcledError:
            pass
    return _password_grant()["access_token"]


# --- data pulls ---------------------------------------------------------------

def _read_page(params: dict, page: int) -> list[dict]:
    """Fetch one page of /api/acled/read. Retries once on a 401 (token refresh)."""
    q = dict(params, _format="json", limit=_PAGE_SIZE, page=page)
    for attempt in (1, 2):
        headers = {"Authorization": f"Bearer {_access_token()}"}
        resp = requests.get(_READ_URL, headers=headers, params=q, timeout=120)
        if resp.status_code == 401 and attempt == 1:
            # Force a re-mint on the next _access_token() call, then retry once.
            _write_token_state({})
            continue
        if not resp.ok:
            raise AcledError(f"ACLED read failed ({resp.status_code}): {resp.text[:200]}")
        body = resp.json()
        if not body.get("success", True):
            raise AcledError(f"ACLED error: {body.get('messages') or body}")
        return body.get("data", [])
    raise AcledError("ACLED read failed after token refresh (still 401).")


def fetch_events(
    start: str,
    end: str,
    *,
    country: str = "Syria",
    admin1: str | None = None,
    extra: dict | None = None,
) -> list[dict]:
    """Conflict events over [start, end] (inclusive), cached/checkpointed per page.

    Filters by ``country`` (and optional ``admin1``); ``extra`` passes any further
    ACLED read params. Pages are fetched until a short page signals the end; each
    page is its own cache unit, so an interrupted paged pull resumes (§9).
    """
    params: dict = {
        "country": country,
        "event_date": f"{start}|{end}",
        "event_date_where": "BETWEEN",
    }
    if admin1:
        params["admin1"] = admin1
    if extra:
        params.update(extra)

    rows: list[dict] = []
    page = 1
    while True:
        sig = ("read", country, admin1, start, end, tuple(sorted((extra or {}).items())), page)
        data, was_cached = _cache.cached(
            sig, lambda p=page: _read_page(params, p), meta={"page": page}
        )
        rows.extend(data)
        # Stop at the first short/empty page. A cached short page also terminates.
        if len(data) < _PAGE_SIZE:
            break
        page += 1
    return rows


def fetch_events_for_aoi(aoi_id: str, start: str, end: str, **kw) -> list[dict]:
    """Events filtered to a canonical AOI's ACLED admin1 (best-effort mapping)."""
    admin1 = ACLED_ADMIN1.get(aoi_id)
    if admin1 is None:
        raise AcledError(f"No ACLED admin1 mapping for AOI '{aoi_id}'.")
    return fetch_events(start, end, admin1=admin1, **kw)


def distinct_admin1(country: str = "Syria", *, sample_start: str = "2025-01-01",
                     sample_end: str = "2025-12-31") -> list[str]:
    """Live helper: distinct ``admin1`` strings for a country (confirm AOI mapping)."""
    rows = fetch_events(sample_start, sample_end, country=country)
    return sorted({r.get("admin1", "") for r in rows if r.get("admin1")})
