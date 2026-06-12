"""Pipeline B — burn scar + severity → damaged_cropland_ha (docs/STRUCTURE.md §4).

Sentinel-2 dNBR for scar + severity, classified into the pinned per-phenomenon
fire severity bins (DEC-009, Key & Benson / USGS FIREMON), intersected with the
canonical cropland definition (DEC-015) and confirmed by VIIRS active-fire
proximity (DEC-031) to get burned-*cropland* hectares. Emits
``DamageRecord(phenomenon=FIRE, validation_status=unvalidated)`` into the shared
schema (§3.2). Tier-2 human-gated (§6): a human validates against Copernicus EMS
EMSR811 (PAX Sentinel-2 methodology as precedent) before anything downstream
consumes these records — no agent flips ``validation_status``.

Method (kept deliberately simple — 80/20):
  * NBR = (B8 − B12)/(B8 + B12) on cloud-masked S2_SR_HARMONIZED median composites.
  * dNBR = NBR_pre − NBR_post (burned vegetation → NBR drops → dNBR > 0).
  * Severity bins per DEC-009: <0.10 unburned · 0.10 low · 0.27 moderate_low ·
    0.44 moderate_high · 0.66 high.
  * A dNBR scar is counted as fire damage ONLY where it is within 375 m of a VIIRS
    hotspot (DEC-031) AND on cropland. Reported under BOTH union and intersection
    cropland (DEC-015) as a sensitivity range.

GEE IDs (verified S2/DEC-013): COPERNICUS/S2_SR_HARMONIZED, ESA/WorldCover/v200,
  GOOGLE/DYNAMICWORLD/V1.
"""

from __future__ import annotations

# dNBR severity thresholds (DEC-009). Class ints 1..4 are the *damage* classes;
# 0 (unburned, dNBR<0.10) is the schema's zero-damage class and is not summed.
DNBR_BREAKS = (0.10, 0.27, 0.44, 0.66)
SEVERITY_BY_CLASS = {1: "low", 2: "moderate_low", 3: "moderate_high", 4: "high"}

# Cropland definition — identical to the human-reviewed mask (DEC-015).
_WC_CROPLAND = 40           # ESA WorldCover v200 cropland class
_DW_CROPS_THRESH = 0.35     # Dynamic World annual-mean crops prob (2021 ref year)
_DW_YEAR = ("2021-01-01", "2022-01-01")

_S2 = "COPERNICUS/S2_SR_HARMONIZED"
_SCL_BAD = (3, 8, 9, 10, 11)  # shadow, cloud-med, cloud-high, cirrus, snow


# --- cropland (DEC-015 definition, server-side) -------------------------------

def cropland_masks():
    """Return (union, intersection) ee.Image binary cropland masks per DEC-015.

    union = WorldCover-cls40 OR DW-crops>0.35; intersection = AND. These apply
    the *same pinned definition* as the canonical ``aois/cropland_mask.tif`` — the
    driver cross-checks their area against ``aois/_mask_stats.json`` to prove
    equivalence to the human-reviewed artifact before any hectares are trusted.
    """
    import ee

    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    wc40 = wc.eq(_WC_CROPLAND)
    dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
          .filterDate(*_DW_YEAR).select("crops").mean())
    dw_crop = dw.gt(_DW_CROPS_THRESH)
    union = wc40.Or(dw_crop).rename("cropland")
    inter = wc40.And(dw_crop).rename("cropland")
    return union.selfMask(), inter.selfMask()


# --- Sentinel-2 NBR / dNBR ----------------------------------------------------

def _s2_nbr(geom, start: str, end: str, *, max_cloud: float = 60.0):
    """Cloud-masked S2 median NBR over [start, end] within geom."""
    import ee

    def _mask(img):
        scl = img.select("SCL")
        good = scl.neq(_SCL_BAD[0])
        for v in _SCL_BAD[1:]:
            good = good.And(scl.neq(v))
        return img.updateMask(good)

    col = (ee.ImageCollection(_S2)
           .filterBounds(geom).filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
           .map(_mask))
    return col.map(lambda i: i.normalizedDifference(["B8", "B12"]).rename("NBR")).median()


def dnbr_image(geom, pre: tuple[str, str], post: tuple[str, str]):
    """dNBR = NBR_pre − NBR_post over geom (burned → positive)."""
    pre_nbr = _s2_nbr(geom, *pre)
    post_nbr = _s2_nbr(geom, *post)
    return pre_nbr.subtract(post_nbr).rename("dNBR")


def severity_class_image(dnbr):
    """dNBR → integer severity class image (1..4 damage; unburned masked out).

    Class = number of DEC-009 thresholds the dNBR exceeds (0=unburned, 1=low,
    2=moderate_low, 3=moderate_high, 4=high). Built by summing threshold
    comparisons so the result inherits dNBR's projection (a constant-image base
    would have none — the reduceResolution lesson from DEC-018).
    """
    lo, ml, mh, hi = DNBR_BREAKS
    sev = (dnbr.gte(lo).add(dnbr.gte(ml)).add(dnbr.gte(mh)).add(dnbr.gte(hi))
           .rename("sev"))
    return sev.selfMask()  # drop class 0 (unburned) — not a damage class


# --- burned-cropland area by severity ----------------------------------------

def burned_cropland_ha(dnbr, near_fire, cropland, region, *, scale: float = 20.0) -> dict[int, float]:
    """Hectares of fire-confirmed, cropland dNBR per severity class within region.

    severity ∩ near_fire ∩ cropland, summed as true pixel area grouped by class.
    Returns {class_int: hectares} for the damage classes present.
    """
    import ee

    sev = severity_class_image(dnbr).updateMask(near_fire).updateMask(cropland)
    img = ee.Image.pixelArea().addBands(sev)
    grouped = img.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="sev"),
        geometry=region,
        scale=scale,
        maxPixels=int(1e10),
        bestEffort=True,
    ).getInfo()
    out: dict[int, float] = {}
    for g in grouped.get("groups", []):
        out[int(g["sev"])] = g["sum"] / 1e4  # m² → ha
    return out


def cropland_area_ha(cropland, region, *, scale: float = 30.0) -> float:
    """Total cropland hectares within region (for the canonical-mask cross-check)."""
    import ee

    a = (ee.Image.pixelArea().updateMask(cropland)
         .reduceRegion(reducer=ee.Reducer.sum(), geometry=region,
                       scale=scale, maxPixels=int(1e10), bestEffort=True)
         .getInfo())
    return (a.get("area") or 0.0) / 1e4
