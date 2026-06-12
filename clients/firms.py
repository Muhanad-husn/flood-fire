"""FIRMS active-fire client — VIIRS 375 m, NOT MODIS (docs/STRUCTURE.md §9, DEC-006).

Detection uses the FIRMS **area** REST API with a free ``MAP_KEY``; VIIRS only
(``VIIRS_SNPP_NRT`` / ``VIIRS_NOAA20_NRT`` / ``VIIRS_NOAA21_NRT`` for NRT, the
``*_SP`` products for the science-quality archive). MODIS is never used for
detection — it is monthly burned-area context only, handled elsewhere.

Every pull is cached and checkpointed (§9): the request window is split into
≤5-day chunks (the area API's per-request cap), and each ``source × chunk`` is a
cache unit. A retry or resume returns cached chunks without re-pulling. A local
:class:`RateLimiter` tracks the 5,000-transaction / 10-minute budget per key and
surfaces headroom, so the client backs off before NASA returns a 429.

    from clients.firms import fetch_hotspots
    rows = fetch_hotspots("hasakah", "2026-05-01", "2026-07-31")
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Iterable

import requests

from clients._common import Cache, RateLimiter, aoi_bbox_str, secret

_AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}/{date}"
_AVAIL_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{key}/{source}"

# VIIRS 375 m only (DEC-006). NRT products for the live window; SP for archive.
VIIRS_NRT = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
VIIRS_SP = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP")

_MAX_DAY_RANGE = 5  # FIRMS area-API hard cap per request (API enforces [1..5] as of 2026-06; was 10)
_RATE_LIMIT = 5000
_RATE_WINDOW_S = 600

_cache = Cache("firms")
_limiter = RateLimiter("firms", limit=_RATE_LIMIT, window_s=_RATE_WINDOW_S)


class FirmsError(RuntimeError):
    """A FIRMS request failed or the MAP_KEY is invalid/exhausted."""


def _map_key() -> str:
    # Env MAP_KEY overrides secrets.toml [firms].map_key (README convention).
    return secret("firms", "map_key", env="MAP_KEY")


def _chunks(start: str, end: str) -> list[tuple[str, int]]:
    """Split [start, end] into (chunk_end_date, day_range) units of ≤10 days.

    The area API takes an *end date* and a look-back ``day_range``; we tile the
    window from ``start`` forward so each unit is deterministic and cacheable.
    """
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    if d1 < d0:
        raise ValueError(f"end {end} precedes start {start}")
    out: list[tuple[str, int]] = []
    cur = d0
    while cur <= d1:
        span = min(_MAX_DAY_RANGE, (d1 - cur).days + 1)
        chunk_end = cur + timedelta(days=span - 1)
        out.append((chunk_end.isoformat(), span))
        cur = chunk_end + timedelta(days=1)
    return out


def _parse_csv(text: str, *, source: str, aoi_id: str | None) -> list[dict]:
    """Parse a FIRMS area-CSV response into detection dicts (drops empty pulls)."""
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        row["source"] = source
        if aoi_id is not None:
            row["aoi_id"] = aoi_id
        rows.append(row)
    return rows


def _fetch_chunk(bbox: str, source: str, chunk_end: str, days: int) -> str:
    """One area-API transaction → raw CSV text. Records rate-limit usage."""
    if _limiter.headroom() < days:
        raise FirmsError(
            f"FIRMS rate-limit headroom ({_limiter.headroom()}) below this request "
            f"({days} day-transactions). Wait out the {_RATE_WINDOW_S // 60}-min window."
        )
    url = _AREA_URL.format(
        key=_map_key(), source=source, bbox=bbox, days=days, date=chunk_end
    )
    resp = requests.get(url, timeout=120)
    if not resp.ok:
        raise FirmsError(f"FIRMS area request failed ({resp.status_code}): {resp.text[:200]}")
    # FIRMS returns plain text (e.g. "Invalid MAP_KEY") with 200 on key errors.
    if resp.text.lstrip().lower().startswith("invalid"):
        raise FirmsError(f"FIRMS rejected the request: {resp.text[:200]}")
    _limiter.record(days)  # multi-day request counts as multiple transactions (§9)
    return resp.text


def fetch_bbox(
    bbox: str,
    start: str,
    end: str,
    *,
    sources: Iterable[str] = VIIRS_NRT,
    aoi_id: str | None = None,
) -> list[dict]:
    """VIIRS hotspots in a ``W,S,E,N`` bbox over [start, end] (cached/checkpointed).

    Each ``source × ≤10-day chunk`` is fetched through the cache; only missing
    units hit the network, so a retry never re-pulls (§9).
    """
    out: list[dict] = []
    for source in sources:
        for chunk_end, days in _chunks(start, end):
            text, _was_cached = _cache.cached(
                ("area", source, bbox, chunk_end, days),
                lambda s=source, ce=chunk_end, d=days: _fetch_chunk(bbox, s, ce, d),
                text=True,
                meta={"source": source, "bbox": bbox, "chunk_end": chunk_end, "days": days},
            )
            out.extend(_parse_csv(text, source=source, aoi_id=aoi_id))
    return out


def fetch_hotspots(
    aoi_id: str,
    start: str,
    end: str,
    *,
    sources: Iterable[str] = VIIRS_NRT,
) -> list[dict]:
    """VIIRS hotspots for a canonical AOI (§3.1) over [start, end].

    Resolves the AOI bbox from ``aois/governorates.geojson`` — no AOI is
    redefined here (§3.1) — then delegates to :func:`fetch_bbox`.
    """
    return fetch_bbox(
        aoi_bbox_str(aoi_id), start, end, sources=sources, aoi_id=aoi_id
    )


def data_availability(source: str = "VIIRS_SNPP_NRT") -> dict[str, str]:
    """Return ``{min_date, max_date}`` for a product — also validates the key.

    Cheap, un-cached metadata call (doubles as a MAP_KEY liveness check).
    """
    url = _AVAIL_URL.format(key=_map_key(), source=source)
    resp = requests.get(url, timeout=60)
    if not resp.ok:
        raise FirmsError(f"FIRMS availability check failed ({resp.status_code}).")
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    if not rows:
        raise FirmsError(f"No availability for source {source} (bad key or product?).")
    r = rows[0]
    return {"min_date": r.get("min_date", ""), "max_date": r.get("max_date", "")}


def rate_limit_headroom() -> int:
    """Transactions still available in the current 10-minute window (§9)."""
    return _limiter.headroom()
