"""Build the W2 2025-drought baseline layers (docs/STRUCTURE.md §3.3).

Reference layers, computed ONCE (not per run); all 2026 damage is expressed
relative to them. Three artifacts:

  * baseline/rainfall_deficit.csv   — CHIRPS Nov 2024-May 2025 season total vs a
                                      1991-2020 climatological normal, per AOI.
  * baseline/ndvi_anomaly_2025.tif  — Sentinel-2 growing-season (Mar-May) peak
                                      NDVI 2025 minus the 2019-2024 mean, on
                                      cropland (union), 30 m EPSG:32637.
  * baseline/production_baseline.csv — the FAO/GIEWS ~1.2 Mt national cereal
                                      floor disaggregated across all 14 Syrian
                                      governorates by cropland-area share; the 4
                                      study AOIs are flagged. Sums to the floor.

Pinned context (docs/STRUCTURE.md §3.3, DEC-001): baseline/context ONLY — pre-2026
data is never the subject of analysis. Cropland = `aois/cropland_mask.tif` value
in {1,2,3} (union, DEC-015). CHIRPS ID is `UCSB-CHG/CHIRPS/DAILY` (DEC-013). Large
rasters export via geedim tiled getPixels, not toDrive (DEC-016).

Run (any subset):
    conda run -n f_f python baseline/build_baseline.py rainfall
    conda run -n f_f python baseline/build_baseline.py ndvi
    conda run -n f_f python baseline/build_baseline.py production
    conda run -n f_f python baseline/build_baseline.py all
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from clients.gee_auth import initialize  # noqa: E402

# ---- shared constants (kept consistent with aois/build_aois.py) -------------
CRS = "EPSG:32637"            # UTM 37N — same grid family as cropland_mask.tif
SCALE = 30                    # metres
NODATA_F = -9999.0            # float nodata for the NDVI anomaly raster
DW_CROPS_THRESHOLD = 0.35     # DEC-015 — cropland DW threshold (reused below)
WC_YEAR = "2021"             # WorldCover v200 reference year (cropland definition)

# CHIRPS rainfall-deficit window (§3.3, pinned) and climatological normal.
SEASON_START = ("2024-11-01", "2025-06-01")   # Nov 2024 .. May 2025 (end exclusive)
CLIM_START_YEARS = (1991, 2020)               # season start-years, inclusive -> 30 seasons

# NDVI growing-season window (winter wheat peak / critical final stage, PRODUCT §2)
NDVI_MONTHS = (3, 6)          # Mar 1 .. Jun 1 (end exclusive) growing-season max
NDVI_NORMAL_YEARS = (2019, 2024)  # S2_SR_HARMONIZED archive limit (excludes 2025)

# FAO/GIEWS 2025 national cereal floor (PRODUCT.md §2). ~1.2 Mt, worst in ~60 yr.
NATIONAL_CEREAL_FLOOR_MT = 1.2

BASE = REPO / "baseline"
AOIS_DIR = REPO / "aois"
GOV_PATH = AOIS_DIR / "governorates.geojson"
MASK_PATH = AOIS_DIR / "cropland_mask.tif"

# Canonical study AOIs (mirror of build_aois.AOIS) — gaul = GAUL ADM1_NAME.
AOIS = [
    {"aoi_id": "deir_ez_zor", "name": "Deir ez-Zor", "gaul": "Dayr_Az_Zor"},
    {"aoi_id": "raqqa",       "name": "Raqqa",       "gaul": "Raqqa"},
    {"aoi_id": "hasakah",     "name": "Hasakah",     "gaul": "Hassakeh"},
    {"aoi_id": "latakia",     "name": "Latakia",     "gaul": "Lattakia"},
]
AOI_IDS = {a["gaul"]: a["aoi_id"] for a in AOIS}


# ----------------------------------------------------------------------------
# Earth Engine helpers
# ----------------------------------------------------------------------------
def _syria_l1(ee):
    return (ee.FeatureCollection("FAO/GAUL/2015/level1")
            .filter(ee.Filter.eq("ADM0_NAME", "Syrian Arab Republic")))


def cropland_union_img(ee):
    """Server-side cropland mask (union, DEC-015): 1 where DW or WorldCover crop.

    Mirrors aois/build_aois.cropland_categorical but reduced to a binary union
    so it can mask other layers. 10 m native; callers reduceResolution as needed.
    """
    wc_crop = ee.Image(f"ESA/WorldCover/v200/{WC_YEAR}").select("Map").eq(40)
    dw_crop = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
               .filterDate(f"{WC_YEAR}-01-01", f"{int(WC_YEAR)+1}-01-01")
               .select("crops").mean().gt(DW_CROPS_THRESHOLD))
    return wc_crop.unmask(0).Or(dw_crop.unmask(0)).rename("cropland")


# ----------------------------------------------------------------------------
# 1) CHIRPS rainfall deficit  ->  baseline/rainfall_deficit.csv
# ----------------------------------------------------------------------------
def _chirps_season_sum(ee, chirps, start_y):
    """Sum of CHIRPS daily precip over a Nov(start_y)..May(start_y+1) season."""
    start = ee.Date.fromYMD(start_y, 11, 1)
    end = ee.Date.fromYMD(ee.Number(start_y).add(1), 6, 1)
    return chirps.filterDate(start, end).sum()


def build_rainfall_deficit(ee):
    print("== rainfall deficit (CHIRPS Nov2024-May2025 vs 1991-2020) ==")
    chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")  # DEC-013
    syria = _syria_l1(ee)

    actual = chirps.filterDate(*SEASON_START).sum()
    y0, y1 = CLIM_START_YEARS
    seasons = ee.List.sequence(y0, y1)  # 30 start-years -> 30 seasons
    clim = ee.ImageCollection(
        seasons.map(lambda y: _chirps_season_sum(ee, chirps, ee.Number(y)))
    ).mean()

    rows = []
    for a in AOIS:
        geom = syria.filter(ee.Filter.eq("ADM1_NAME", a["gaul"])).first().geometry()
        # CHIRPS native ~5566 m; AOI-mean rainfall (cropland-masking at 5.5 km is
        # meaningless — pixel >> field). Documented in baseline/README.md.
        act = actual.reduceRegion(ee.Reducer.mean(), geom, scale=5566,
                                  maxPixels=1e9).get("precipitation")
        cli = clim.reduceRegion(ee.Reducer.mean(), geom, scale=5566,
                                maxPixels=1e9).get("precipitation")
        act_v = round(ee.Number(act).getInfo(), 1)
        cli_v = round(ee.Number(cli).getInfo(), 1)
        deficit = round(act_v - cli_v, 1)
        pct = round(100.0 * deficit / cli_v, 1)
        rows.append({
            "aoi_id": a["aoi_id"], "name": a["name"],
            "season_total_mm_2024_2025": act_v,
            "climatology_mm_1991_2020": cli_v,
            "deficit_mm": deficit,
            "deficit_pct": pct,
        })
        print(f"  {a['name']:12s} actual={act_v:6.1f}  normal={cli_v:6.1f}  "
              f"deficit={deficit:6.1f} mm ({pct:+.1f}%)")

    out = BASE / "rainfall_deficit.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {out}")
    return rows


# ----------------------------------------------------------------------------
# 2) Production baseline  ->  baseline/production_baseline.csv
# ----------------------------------------------------------------------------
def build_production_baseline(ee):
    print("== production baseline (GIEWS ~1.2 Mt by cropland-area share) ==")
    syria = _syria_l1(ee)
    crop = cropland_union_img(ee)
    # cropland area per governorate = mean(cropland binary) x governorate area.
    # A single reduceRegions(sum, 30 m) over all 14 governorates times out, so we
    # loop and use the MEAN fraction at a coarse sampling scale (300 m): the
    # fraction is scale-robust and the share (a ratio) is unaffected, while the
    # call is cheap. ADM1 names come from the same GAUL L1 features.
    names = syria.aggregate_array("ADM1_NAME").getInfo()
    recs = []
    for nm in names:
        geom = syria.filter(ee.Filter.eq("ADM1_NAME", nm)).first().geometry()
        frac = ee.Number(crop.reduceRegion(
            ee.Reducer.mean(), geom, scale=300, maxPixels=1e10, bestEffort=True
        ).get("cropland")).getInfo() or 0.0
        area_ha = geom.area(maxError=30).divide(1e4).getInfo()
        ha = frac * area_ha
        recs.append({"gaul_adm1": nm, "crop_ha": ha})
        print(f"  {nm:18s} frac={frac:6.3f}  crop_ha={ha:11,.0f}")
    total_ha = sum(r["crop_ha"] for r in recs)

    rows = []
    floor_t = NATIONAL_CEREAL_FLOOR_MT * 1e6  # Mt -> tonnes
    for r in sorted(recs, key=lambda x: -x["crop_ha"]):
        share = r["crop_ha"] / total_ha if total_ha else 0.0
        prod_t = round(floor_t * share)
        rows.append({
            "gaul_adm1": r["gaul_adm1"],
            "aoi_id": AOI_IDS.get(r["gaul_adm1"], ""),
            "is_study_aoi": r["gaul_adm1"] in AOI_IDS,
            "cropland_ha": round(r["crop_ha"]),
            "cropland_share": round(share, 5),
            "cereal_production_2025_t": prod_t,
        })

    out = BASE / "production_baseline.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    tot_t = sum(r["cereal_production_2025_t"] for r in rows)
    aoi_t = sum(r["cereal_production_2025_t"] for r in rows if r["is_study_aoi"])
    print(f"  governorates={len(rows)}  national_total={tot_t:,} t "
          f"(floor {floor_t:,.0f} t)  study-AOI portion={aoi_t:,} t "
          f"({100*aoi_t/tot_t:.0f}%)")
    print(f"  -> {out}")
    return rows


# ----------------------------------------------------------------------------
# 3) NDVI anomaly raster  ->  baseline/ndvi_anomaly_2025.tif
# ----------------------------------------------------------------------------
def _s2_growing_max_ndvi(ee, geom, year):
    """Cloud-masked S2 growing-season (Mar-May) MAX NDVI for `year` over geom."""
    m0, m1 = NDVI_MONTHS
    start = ee.Date.fromYMD(year, m0, 1)
    end = ee.Date.fromYMD(year, m1, 1)

    def mask_ndvi(img):
        scl = img.select("SCL")
        # keep vegetation/bare/water/unclassified; drop cloud, shadow, cirrus, snow
        good = (scl.neq(3).And(scl.neq(8)).And(scl.neq(9))
                .And(scl.neq(10)).And(scl.neq(11)).And(scl.neq(1)))
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
        # resample so the later reproject to 30 m interpolates (bilinear) rather
        # than nearest-samples a single 10 m pixel.
        return ndvi.updateMask(good).resample("bilinear")

    coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom).filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
            .map(mask_ndvi))
    return coll.max().rename("ndvi")  # peak greenness over the season


def ndvi_anomaly_img(ee, geom):
    """2025 growing-season peak NDVI minus the 2019-2024 mean, on cropland union."""
    y2025 = _s2_growing_max_ndvi(ee, geom, 2025)
    y0, y1 = NDVI_NORMAL_YEARS
    normal = ee.ImageCollection([
        _s2_growing_max_ndvi(ee, geom, y) for y in range(y0, y1 + 1)
    ]).mean()
    anomaly = y2025.subtract(normal).rename("ndvi_anomaly")
    # 10 m -> 30 m by bilinear reproject (the S2 NDVI is resample('bilinear')).
    # reduceResolution can't be used here: the .max() composite has no fixed
    # default projection. Cropland masking is enforced LOCALLY against
    # aois/cropland_mask.tif in build_ndvi_anomaly (authoritative, DEC-015).
    return anomaly.reproject(crs=CRS, scale=SCALE).clip(geom).toFloat()


def _export_ndvi_tile(ee, geom, name, out, attempts=4):
    import geedim  # noqa: F401 — registers .gd accessor
    img = ndvi_anomaly_img(ee, geom)
    img = img.gd.prepareForExport(crs=CRS, scale=SCALE, region=geom,
                                  dtype="float32", resampling="near")
    last = None
    for k in range(attempts):
        try:
            img.gd.toGeoTIFF(out, overwrite=True, nodata=NODATA_F,
                             max_tile_size=1, max_tile_dim=1500, max_requests=16)
            return
        except Exception as exc:
            last = exc
            print(f"    [{name}] attempt {k+1}/{attempts} failed: {repr(exc)[:120]}")
            time.sleep(8 * (k + 1))
    raise RuntimeError(f"NDVI export failed for {name}: {last}")


def build_ndvi_anomaly(ee):
    print("== NDVI anomaly 2025 (S2 Mar-May peak; 2025 - mean(2019-2024)) ==")
    import numpy as np
    import rasterio
    from rasterio.merge import merge
    from rasterio.features import geometry_mask
    from rasterio.warp import reproject, Resampling
    import geopandas as gpd

    syria = _syria_l1(ee)
    tmp = BASE / "_ndvi_tiles"
    tmp.mkdir(exist_ok=True)
    gov = gpd.read_file(GOV_PATH).to_crs(CRS)
    geom_by_id = {r["aoi_id"]: r.geometry for _, r in gov.iterrows()}

    # Export per AOI (server-side already cropland-masked; clip polygon locally).
    for a in AOIS:
        out = tmp / f"{a['aoi_id']}.tif"
        if out.exists():
            print(f"  [{a['name']}] tile exists, skip pull")
            continue
        geom = syria.filter(ee.Filter.eq("ADM1_NAME", a["gaul"])).first().geometry()
        print(f"  exporting {a['name']} ...")
        _export_ndvi_tile(ee, geom, a["name"], str(out))

    # Mask each tile to the local cropland mask (resampled to the NDVI grid,
    # nearest) AND to the AOI polygon, then mosaic. "Resample the mask, don't
    # redefine cropland" (S3 handoff). Belt-and-suspenders vs server-side mask.
    with rasterio.open(MASK_PATH) as mds:
        mask_arr = mds.read(1)
        mask_crs, mask_transform = mds.crs, mds.transform

    parts = []
    for a in AOIS:
        tile = tmp / f"{a['aoi_id']}.tif"
        clipped = tmp / f"{a['aoi_id']}_clip.tif"
        with rasterio.open(tile) as ds:
            arr = ds.read(1).astype("float32")
            prof = ds.profile
            # resample cropland mask onto this tile's grid
            mask_on = np.zeros(arr.shape, dtype="uint8")
            reproject(source=mask_arr, destination=mask_on,
                      src_transform=mask_transform, src_crs=mask_crs,
                      dst_transform=ds.transform, dst_crs=ds.crs,
                      resampling=Resampling.nearest, src_nodata=255, dst_nodata=0)
            inside = geometry_mask([geom_by_id[a["aoi_id"]].__geo_interface__],
                                   out_shape=arr.shape, transform=ds.transform,
                                   invert=True)
            is_crop = np.isin(mask_on, (1, 2, 3)) & inside
            arr = np.where(is_crop & (arr != NODATA_F), arr, NODATA_F).astype("float32")
        prof.update(dtype="float32", nodata=NODATA_F, compress="deflate",
                    predictor=3, tiled=True)
        with rasterio.open(clipped, "w", **prof) as dst:
            dst.write(arr, 1)
        parts.append(clipped)
        valid = arr[arr != NODATA_F]
        if valid.size:
            print(f"  {a['name']:12s} cropland px={valid.size:>9,}  "
                  f"mean anomaly={valid.mean():+.3f}  median={np.median(valid):+.3f}")

    srcs = [rasterio.open(p) for p in parts]
    mosaic, transform = merge(srcs, nodata=NODATA_F)
    profile = srcs[0].profile
    profile.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=transform,
                   nodata=NODATA_F, count=1, dtype="float32",
                   compress="deflate", predictor=3, tiled=True)
    for s in srcs:
        s.close()
    out = BASE / "ndvi_anomaly_2025.tif"
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(mosaic[0], 1)
        dst.update_tags(
            layer="2025 growing-season NDVI anomaly on cropland (union)",
            method="S2_SR_HARMONIZED Mar-May per-pixel MAX NDVI; "
                   "anomaly = 2025 - mean(2019..2024)",
            cropland="aois/cropland_mask.tif value in {1,2,3} (union, DEC-015)",
            crs=CRS, scale_m=str(SCALE), nodata=str(NODATA_F),
            note="baseline/context only (DEC-001); negative = drought stress")
    print(f"  -> {out}  shape={mosaic.shape[1]}x{mosaic.shape[2]}")


# ----------------------------------------------------------------------------
def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    import ee
    initialize()
    if what in ("rainfall", "all"):
        build_rainfall_deficit(ee)
    if what in ("production", "all"):
        build_production_baseline(ee)
    if what in ("ndvi", "all"):
        build_ndvi_anomaly(ee)
    print("done.")


if __name__ == "__main__":
    main()
