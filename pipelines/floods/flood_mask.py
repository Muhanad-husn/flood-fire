"""Pipeline A — Sentinel-1 SAR flood-extent masks (docs/STRUCTURE.md §4 Pipeline A).

Window: March–June 2026 (April floods/hailstorms + late-May Euphrates surge).
AOIs: Deir ez-Zor, Raqqa, Hasakah.

Sentinel-1 SAR is **load-bearing** (extent through cloud); optical (Sentinel-2 +
Dynamic World) is confirmatory only (§9, DEC-006). Method (Sentinel-1
change-detection, tuned conservative for an agricultural floodplain):

  * Per event date, compare the in-event acquisition against an **in-season
    per-relative-orbit median reference** (the median of all window acquisitions
    of the SAME relative orbit). In-season removes crop-phenology bias — a
    dry-summer reference flagged dense spring canopy as "flood" across whole
    governorates (~10⁵ ha of false positives); the seasonal median is the honest
    no-flood backdrop. Per-orbit keeps the incidence-angle geometry matched.
  * Flood = backscatter **drop** ≥ CHANGE_DB vs the seasonal median (water is
    specular/dark) **AND** the in-event VV **and** VH are both dark enough to be
    open water (dual-pol AND — the open-water signature, not a single-band OR
    that doubles false positives).
  * Constrain to the **floodplain**: HAND (height above nearest drainage, MERIT
    Hydro) < HAND_MAX_M. River floods sit in low-lying terrain near drainage;
    the dominant residual false positive — smooth **dry harvested fields** in
    June, which are radar-dark and mimic water — sits on uplands above drainage.
    HAND removes them while keeping the documented Euphrates/Khabur riverine
    flood. (Pluvial upland flooding is correspondingly under-captured — a
    documented limitation in the validation packet.)
  * Subtract JRC Global Surface Water **permanent** water (occurrence > 50 %), so
    the permanent river is never counted as damage (the `permanent_excluded`
    severity class, DEC-009).
  * Remove steep slopes (GLO-30 DEM > SLOPE_DEG°) — radar-shadow false positives.
  * Speckle / lone-pixel cleanup is done **locally** after export (connectivity),
    not server-side, to avoid EE projection constraints on a composite.

Known limitation (carried into the validation packet): change-detection on a
backscatter **drop** captures **open standing water**; flooded vegetation can
*raise* VV via double-bounce and is under-detected here — that is precisely why
optical/Dynamic World is the confirmatory layer (§9). Claims stay proportionate.

This module holds the server-side ee.Image builders only (no I/O); orchestration,
export, hectare accounting and record emission live in ``cropland_flooded.py``.

GEE IDs (verified live S2, DEC-013): COPERNICUS/S1_GRD, JRC/GSW1_4/GlobalSurfaceWater,
COPERNICUS/DEM/GLO30, GOOGLE/DYNAMICWORLD/V1, ESA/WorldCover/v200.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Reuse the ONE server-side cropland definition (DEC-015) rather than redefining
# it (§3.1 — no module redefines the shared cropland asset). The authoritative
# hectare numbers downstream use the local human-reviewed aois/cropland_mask.tif;
# this server-side union is only for the cheap event-screening pass.
from baseline.build_baseline import cropland_union_img  # noqa: E402

# ---- tunable detection parameters (DEC — recorded in tracking/DECISIONS.md) ---
FLOOD_WINDOW = ("2026-03-01", "2026-06-13")   # §4 Pipeline A window; also the
                                              # in-season reference period (median).

CHANGE_DB = 4.0      # min backscatter drop (seasonal-median − event, dB)
WATER_VV_DB = -18.0  # in-event VV open-water threshold (both pols must be dark)
WATER_VH_DB = -24.0  # in-event VH open-water threshold
SLOPE_DEG = 5.0      # drop slopes steeper than this (radar shadow / not floodplain)
HAND_MAX_M = 15.0    # floodplain constraint: keep only height-above-drainage < this
GSW_PERMANENT_PCT = 50  # JRC GSW occurrence > this = permanent water (subtracted)
SMOOTH_M = 50        # focal-mean speckle smoothing radius (metres)

S1_ID = "COPERNICUS/S1_GRD"
GSW_ID = "JRC/GSW1_4/GlobalSurfaceWater"
DEM_ID = "COPERNICUS/DEM/GLO30"
HAND_ID = "MERIT/Hydro/v1_0_1"  # 'hnd' = height above nearest drainage (m)


# ----------------------------------------------------------------------------
def s1_iw(ee, geom, start, end):
    """Sentinel-1 IW GRD, VV+VH, over geom/window (dB backscatter, native ~10 m)."""
    return (ee.ImageCollection(S1_ID)
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .select(["VV", "VH"]))


def _smooth(ee, img):
    """Focal-mean speckle reduction (UN-SPIDER recommended pre-filter)."""
    return img.focal_mean(SMOOTH_M, "circle", "meters")


def acquisition_dates(ee, geom, start=FLOOD_WINDOW[0], end=FLOOD_WINDOW[1]):
    """Sorted unique 'YYYY-MM-dd' S1 acquisition dates over geom in the window."""
    coll = s1_iw(ee, geom, start, end)
    fmt = coll.aggregate_array("system:time_start").map(
        lambda t: ee.Date(t).format("YYYY-MM-dd"))
    return sorted(set(fmt.getInfo()))


def permanent_water(ee):
    """JRC GSW permanent-water mask (occurrence > GSW_PERMANENT_PCT)."""
    return ee.Image(GSW_ID).select("occurrence").gt(GSW_PERMANENT_PCT).unmask(0)


def floodplain(ee):
    """Floodplain mask: HAND < HAND_MAX_M (undefined -> excluded)."""
    return ee.Image(HAND_ID).select("hnd").unmask(9999).lt(HAND_MAX_M)


def _slope(ee):
    dem = (ee.ImageCollection(DEM_ID).select("DEM").mosaic()
           .setDefaultProjection("EPSG:4326", None, 30))
    return ee.Terrain.slope(dem)


def seasonal_ref(ee, geom, orbits):
    """In-season per-relative-orbit median reference (the no-flood backdrop)."""
    coll = (s1_iw(ee, geom, *FLOOD_WINDOW)
            .filter(ee.Filter.inList("relativeOrbitNumber_start", orbits)))
    return _smooth(ee, coll.median())


def flood_binary(ee, geom, date_str, refine=True):
    """Binary flood mask (1 = flooded land, water excluded) for one S1 date.

    Reference = in-season median of the SAME relative orbit(s) acquired on
    `date_str` (phenology- and geometry-matched). Flood = VV drop ≥ CHANGE_DB vs
    that median AND both VV and VH dark enough for open water (dual-pol AND).
    Permanent water and (if refine) steep slope removed. Returned self-masked
    (1 where flood, masked elsewhere), clipped to geom.
    """
    day = ee.Date(date_str)
    event_coll = s1_iw(ee, geom, day, day.advance(1, "day"))
    orbits = event_coll.aggregate_array("relativeOrbitNumber_start").distinct()

    ref = seasonal_ref(ee, geom, orbits)
    ev = _smooth(ee, event_coll.mosaic())

    d_vv = ref.select("VV").subtract(ev.select("VV"))   # +ve = backscatter dropped
    flood = (d_vv.gte(CHANGE_DB)
             .And(ev.select("VV").lt(WATER_VV_DB))
             .And(ev.select("VH").lt(WATER_VH_DB)))     # dual-pol open-water AND

    flood = flood.And(floodplain(ee))                   # HAND floodplain constraint
    flood = flood.And(permanent_water(ee).Not())
    if refine:
        flood = flood.And(_slope(ee).lt(SLOPE_DEG))
    return flood.rename("flood").selfMask().clip(geom)


def flooded_cropland_ha(ee, geom, date_str, scale=150):
    """Coarse flooded-cropland area (ha) for one date — the cheap screening pass.

    No slope refinement (kept light); intersect flood with the server-side
    cropland union (DEC-015). Area summed at `scale` m (screening only — the
    authoritative hectares come from the 30 m local pass in cropland_flooded.py).
    """
    flood = flood_binary(ee, geom, date_str, refine=False)
    crop = cropland_union_img(ee)
    fc = flood.And(crop).rename("fc").selfMask()
    area = (fc.multiply(ee.Image.pixelArea())
            .reduceRegion(ee.Reducer.sum(), geom, scale=scale,
                          maxPixels=1e10, bestEffort=True).get("fc"))
    return ee.Number(area).divide(1e4)  # m² -> ha


def permanent_cropland_ha(ee, geom, scale=150):
    """Permanent-water ∩ cropland area (ha) — context for the exclusion note."""
    perm = permanent_water(ee).rename("p")
    crop = cropland_union_img(ee)
    pc = perm.And(crop).rename("pc").selfMask()
    area = (pc.multiply(ee.Image.pixelArea())
            .reduceRegion(ee.Reducer.sum(), geom, scale=scale,
                          maxPixels=1e10, bestEffort=True).get("pc"))
    return ee.Number(area).divide(1e4)
