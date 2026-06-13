"""Pipeline B — active-fire detection (docs/STRUCTURE.md §4 Pipeline B).

Window: May–July 2026 fire season; July 2025 Latakia (EMSR811) as documented
anchor. AOIs: Hasakah (cropland fires), Latakia (coastal/forest).

Primary detector: FIRMS VIIRS 375 m (NOT MODIS, §9, DEC-006), pulled through the
cached/checkpointed ``clients/firms.py``. MODIS MCD64A1 would be monthly
burned-area context only — it is not used for detection here.

This module is the *detection* half of Pipeline B. It (1) pulls VIIRS hotspots
for an AOI/window, (2) materialises them as a tidy table + GeoDataFrame, and
(3) builds an Earth Engine "near-fire" mask (the hotspot footprint) that
``burn_severity.py`` uses to confirm a Sentinel-2 dNBR scar is fire-related
rather than a harvest/plough false positive (DEC-031).

Data-availability note (2026-06-13): VIIRS NRT covers ~the last 2 months
(2026-04-28 → 2026-06-12 at build time). The 2026 fire window is therefore
scoped to the *available* part, **May 1 – Jun 12 2026**; the May–July season's
July tail is in the simulated future and is flagged, not fabricated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from clients.firms import VIIRS_NRT, VIIRS_SP, fetch_hotspots

# Fire-AOI windows (§4). 2026 windows are clipped to live VIIRS NRT coverage.
FIRE_AOIS = ("hasakah", "latakia")
WINDOW_2026 = ("2026-05-01", "2026-06-12")   # available NRT slice of the May–Jul season
WINDOW_EMSR811 = ("2025-07-01", "2025-07-20")  # Latakia anchor — *_SP archive, validation only

_NUMERIC = ("latitude", "longitude", "bright_ti4", "bright_ti5", "frp", "scan", "track")


def fetch(aoi_id: str, start: str, end: str, *, sources: Iterable[str] = VIIRS_NRT) -> list[dict]:
    """Cached VIIRS hotspots for a canonical AOI/window (delegates to firms client)."""
    return fetch_hotspots(aoi_id, start, end, sources=sources)


def _clean(rows: list[dict]) -> list[dict]:
    """Coerce numeric columns; keep the rest as-is. Drops rows with bad coords."""
    out = []
    for r in rows:
        rec = dict(r)
        ok = True
        for col in _NUMERIC:
            if col in rec and rec[col] not in ("", None):
                try:
                    rec[col] = float(rec[col])
                except (TypeError, ValueError):
                    if col in ("latitude", "longitude"):
                        ok = False
                        break
        if ok:
            out.append(rec)
    return out


def to_gdf(rows: list[dict]):
    """VIIRS rows → GeoDataFrame of points, EPSG:4326 (lazy geopandas import)."""
    import geopandas as gpd
    from shapely.geometry import Point

    rows = _clean(rows)
    geom = [Point(r["longitude"], r["latitude"]) for r in rows]
    return gpd.GeoDataFrame(rows, geometry=geom, crs="EPSG:4326")


def to_ee_points(rows: list[dict]):
    """VIIRS rows → ee.FeatureCollection of points (EPSG:4326), with frp/conf props."""
    import ee

    rows = _clean(rows)
    feats = []
    for r in rows:
        g = ee.Geometry.Point([r["longitude"], r["latitude"]])
        feats.append(ee.Feature(g, {
            "acq_date": r.get("acq_date", ""),
            "confidence": r.get("confidence", ""),
            "frp": r.get("frp", 0.0),
            "source": r.get("source", ""),
        }))
    return ee.FeatureCollection(feats)


def near_fire_mask(rows: list[dict], *, buffer_m: float = 375.0):
    """Earth Engine mask = 1 within ``buffer_m`` of any VIIRS hotspot.

    The buffer defaults to one VIIRS pixel (375 m) — the spatial uncertainty of a
    375 m active-fire detection. ``burn_severity`` AND-combines this with the dNBR
    scar and the cropland mask so only fire-confirmed, cropland dNBR is counted as
    damage (DEC-031). Returns a self-masked image (1 inside, masked outside).
    """
    import ee

    pts = to_ee_points(rows)
    dist = pts.distance(searchRadius=buffer_m + 1).rename("dist")
    return dist.lte(buffer_m).selfMask().rename("near_fire")


def footprint_geometry(rows: list[dict], *, buffer_m: float = 375.0):
    """Union of buffered hotspots — the reduceRegion region that bounds compute.

    Buffering the MultiPoint already unions overlapping circles; reduceRegion
    treats the region as a set, so any residual overlap never double-counts area.
    """
    import ee  # noqa: F401  (kept explicit so the EE dep is obvious)

    return to_ee_points(rows).geometry().buffer(buffer_m)


def bbox_lonlat(rows: list[dict], *, pad_deg: float = 0.02) -> tuple[float, float, float, float]:
    """(W,S,E,N) of the hotspots in degrees, padded — for plotting/thumbnails."""
    rows = _clean(rows)
    lons = [r["longitude"] for r in rows]
    lats = [r["latitude"] for r in rows]
    return (min(lons) - pad_deg, min(lats) - pad_deg,
            max(lons) + pad_deg, max(lats) + pad_deg)


def summary(rows: list[dict]) -> dict:
    """Quick stats for logging/packets."""
    rows = _clean(rows)
    if not rows:
        return {"n": 0}
    dates = sorted({r.get("acq_date", "") for r in rows})
    conf: dict[str, int] = {}
    frps = []
    for r in rows:
        conf[r.get("confidence", "?")] = conf.get(r.get("confidence", "?"), 0) + 1
        if isinstance(r.get("frp"), (int, float)):
            frps.append(r["frp"])
    return {
        "n": len(rows),
        "dates": len(dates),
        "first_date": dates[0],
        "last_date": dates[-1],
        "confidence": conf,
        "frp_mean": round(sum(frps) / len(frps), 2) if frps else None,
        "frp_max": round(max(frps), 2) if frps else None,
    }


def save_hotspots_csv(rows: list[dict], path: str | Path) -> Path:
    """Persist the raw hotspot table to outputs/ (provenance for the packet)."""
    import csv

    rows = _clean(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    cols = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path
