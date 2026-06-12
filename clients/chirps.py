"""CHIRPS daily rainfall client (docs/STRUCTURE.md §5).

Role F/B. GEE collection **`UCSB-CHG/CHIRPS/DAILY`** (DEC-013 — the §5 slash form
``UCSB/CHG/CHIRPS/DAILY`` does not resolve; the provider namespace is hyphenated).
Pulls the daily AOI-mean ``precipitation`` (mm/day) series that feeds the §3.3
baseline rainfall deficit (Nov 2024–May 2025) and the RQ1 rainfall-vs-discharge
decomposition (S9).

CHIRPS pixels are ~5566 m — far larger than a field — so the honest quantity is
the **AOI-mean**, not a cropland-masked value (DEC-017); masking a 5.5 km grid to
30 m cropland is meaningless. The series is reduced server-side in one pass and
cached per ``(aoi_id, start, end)``; a retry returns the cached series without
re-pulling (§9).

    from clients.chirps import fetch_daily
    series = fetch_daily("deir_ez_zor", "2024-11-01", "2025-05-31")
    # -> [{"date": "2024-11-01", "precip_mm": 0.0}, ...]
"""

from __future__ import annotations

from datetime import datetime, timedelta

from clients._common import Cache, load_aois

CHIRPS_ID = "UCSB-CHG/CHIRPS/DAILY"  # DEC-013
_CHIRPS_SCALE_M = 5566  # native ~0.05°
_cache = Cache("chirps")


class ChirpsError(RuntimeError):
    """A CHIRPS/GEE pull failed."""


def _exclusive_end(end: str) -> str:
    """GEE ``filterDate`` upper bound is exclusive; add a day to include ``end``."""
    d = datetime.strptime(end, "%Y-%m-%d").date() + timedelta(days=1)
    return d.isoformat()


def _pull_series(aoi_id: str, start: str, end: str) -> list[dict]:
    """Reduce the CHIRPS daily AOI-mean precip series server-side (one pass)."""
    from clients.gee_auth import initialize

    initialize()
    import ee

    geom = ee.Geometry(load_aois()[aoi_id]["geometry"])
    coll = (
        ee.ImageCollection(CHIRPS_ID)
        .filterDate(start, _exclusive_end(end))
        .filterBounds(geom)
    )

    def per_image(img):
        mean = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=_CHIRPS_SCALE_M,
            maxPixels=int(1e9),
        ).get("precipitation")
        return ee.Feature(None, {
            "date": img.date().format("YYYY-MM-dd"),
            "precip_mm": mean,
        })

    fc = ee.FeatureCollection(coll.map(per_image))
    try:
        dates = fc.aggregate_array("date").getInfo()
        vals = fc.aggregate_array("precip_mm").getInfo()
    except Exception as exc:  # ee.EEException etc.
        raise ChirpsError(f"CHIRPS reduction failed for {aoi_id} [{start}..{end}]: {exc}") from exc
    return [
        {"date": d, "precip_mm": (float(v) if v is not None else None)}
        for d, v in zip(dates, vals)
    ]


def fetch_daily(aoi_id: str, start: str, end: str) -> list[dict]:
    """Daily AOI-mean CHIRPS precipitation (mm/day) over [start, end], cached.

    Returns a list of ``{"date", "precip_mm"}`` ordered by date. The whole series
    for one ``(aoi_id, start, end)`` is a single cache unit; a re-run or retry
    returns it without touching GEE (§9).
    """
    if aoi_id not in load_aois():
        raise ChirpsError(f"Unknown AOI '{aoi_id}'; not in aois/governorates.geojson.")
    series, _was_cached = _cache.cached(
        ("daily", aoi_id, start, end),
        lambda: _pull_series(aoi_id, start, end),
        meta={"collection": CHIRPS_ID, "aoi_id": aoi_id, "start": start, "end": end},
    )
    return series


def season_total_mm(aoi_id: str, start: str, end: str) -> float:
    """Convenience: total CHIRPS precipitation (mm) over the window for an AOI."""
    return sum(r["precip_mm"] for r in fetch_daily(aoi_id, start, end) if r["precip_mm"] is not None)
