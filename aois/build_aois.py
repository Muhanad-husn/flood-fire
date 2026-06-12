"""Build the canonical W1 spatial assets (docs/STRUCTURE.md §3.1, §4).

Reproducible generator for:
  * aois/governorates.geojson  — 4 canonical AOIs (FAO GAUL 2015 L1), EPSG:4326
  * aois/cropland_mask.tif      — reconciled DW x ESA WorldCover, EPSG:32637, 30 m

Cropland reconciliation (DEC, S3): a single categorical raster encodes BOTH the
mask and the per-pixel source disagreement (§3.1 "with disagreement documented"):
    0 = neither   1 = WorldCover-only   2 = Dynamic World-only   3 = both agree
Downstream cropland = value in {1,2,3} (UNION, headline); value == 3 is the
INTERSECTION available for sensitivity bounds. Non-cropland = 0; outside AOI = 255.

Sources (verified live S2, DEC-013): ESA WorldCover v200 cropland = class 40;
Dynamic World cropland = annual-mean `crops` probability > 0.35 over 2021 (the
WorldCover v200 reference year). 10 m -> 30 m via mode reduceResolution.

Run:  conda run -n f_f python aois/build_aois.py
GEE is non-interactive via clients.gee_auth (service account, DEC-012).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from clients.gee_auth import initialize  # noqa: E402

CRS = "EPSG:32637"          # UTM 37N — single CRS for all AOIs (§3.1 "one mask")
SCALE = 30                  # metres; each pixel = 0.09 ha
DW_CROPS_THRESHOLD = 0.35   # annual-mean crops probability cut for DW cropland
WC_YEAR = "2021"            # WorldCover v200 + DW reference year

# Canonical AOIs (§3.1, §4). gaul = FAO GAUL 2015 ADM1_NAME spelling.
AOIS = [
    {"aoi_id": "deir_ez_zor", "name": "Deir ez-Zor", "gaul": "Dayr_Az_Zor", "pipelines": ["floods"]},
    {"aoi_id": "raqqa",       "name": "Raqqa",       "gaul": "Raqqa",       "pipelines": ["floods"]},
    {"aoi_id": "hasakah",     "name": "Hasakah",     "gaul": "Hassakeh",    "pipelines": ["floods", "fires"]},
    {"aoi_id": "latakia",     "name": "Latakia",     "gaul": "Lattakia",    "pipelines": ["fires"]},
]

AOIS_DIR = REPO / "aois"
GOV_PATH = AOIS_DIR / "governorates.geojson"
MASK_PATH = AOIS_DIR / "cropland_mask.tif"
NODATA = 255


def _syria(ee):
    return (ee.FeatureCollection("FAO/GAUL/2015/level1")
            .filter(ee.Filter.eq("ADM0_NAME", "Syrian Arab Republic")))


def cropland_categorical(ee):
    """0/1/2/3 categorical cropland-source raster at native 10 m."""
    wc_crop = ee.Image(f"ESA/WorldCover/v200/{WC_YEAR}").select("Map").eq(40)
    dw_crop = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
               .filterDate(f"{WC_YEAR}-01-01", f"{int(WC_YEAR)+1}-01-01")
               .select("crops").mean().gt(DW_CROPS_THRESHOLD))
    return wc_crop.unmask(0).add(dw_crop.unmask(0).multiply(2)).rename("cropland").toUint8()


def build_governorates(ee) -> dict:
    """Write governorates.geojson; return {aoi_id: ee.Geometry}."""
    syria = _syria(ee)
    feats, geoms = [], {}
    for a in AOIS:
        f = syria.filter(ee.Filter.eq("ADM1_NAME", a["gaul"])).first()
        geom = f.geometry()
        geoms[a["aoi_id"]] = geom
        area_km2 = round(geom.area(10).divide(1e6).getInfo(), 1)
        gj = geom.getInfo()  # EPSG:4326 GeoJSON geometry
        feats.append({
            "type": "Feature",
            "properties": {
                "aoi_id": a["aoi_id"], "name": a["name"],
                "gaul_adm1": a["gaul"], "area_km2": area_km2,
                "pipelines": a["pipelines"],
                "source": "FAO GAUL 2015 level 1 (ADM0=Syrian Arab Republic)",
            },
            "geometry": gj,
        })
        print(f"  {a['name']:12s} area={area_km2:8.1f} km2")
    fc = {"type": "FeatureCollection",
          "name": "syria_2026_aois",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
          "features": feats}
    GOV_PATH.write_text(json.dumps(fc, indent=2), encoding="utf-8")
    print(f"  -> {GOV_PATH}  ({len(feats)} AOIs)")
    return geoms


def export_aoi_mask(ee, geedim, geom, name, out, attempts=4):
    """Export one AOI's 30 m categorical mask, retrying transient EE errors."""
    cat = cropland_categorical(ee)
    # clip(geom) bounds the server-side compute to the AOI; note that geedim fills
    # out-of-polygon pixels with 0 (NOT nodata) on download, so the AUTHORITATIVE
    # polygon clip (outside -> 255) is enforced locally in mosaic_from_tiles().
    cat30 = (cat.reduceResolution(reducer=ee.Reducer.mode(), maxPixels=1024)
             .reproject(crs=CRS, scale=SCALE).clip(geom).toUint8())
    img = cat30.gd.prepareForExport(crs=CRS, scale=SCALE, region=geom,
                                    dtype="uint8", resampling="near")
    last = None
    for k in range(attempts):
        try:
            img.gd.toGeoTIFF(out, overwrite=True, nodata=NODATA,
                             max_tile_size=1, max_tile_dim=1500, max_requests=16)
            return
        except Exception as exc:  # transient "User memory limit exceeded" etc.
            last = exc
            print(f"    [{name}] attempt {k+1}/{attempts} failed: {repr(exc)[:120]}")
            time.sleep(8 * (k + 1))
    raise RuntimeError(f"export failed for {name} after {attempts} attempts: {last}")


def build_cropland_mask(ee, geoms):
    """Export each AOI mask (GEE), then mosaic locally."""
    tmp_dir = AOIS_DIR / "_mask_tiles"
    tmp_dir.mkdir(exist_ok=True)
    import geedim  # registers .gd accessor
    for a in AOIS:
        out = tmp_dir / f"{a['aoi_id']}.tif"
        print(f"  exporting {a['name']} ...")
        export_aoi_mask(ee, geedim, geoms[a["aoi_id"]], a["name"], str(out))
    return mosaic_from_tiles()


def mosaic_from_tiles():
    """Clip each per-AOI tile to its polygon (outside -> NODATA), mosaic, write
    cropland_mask.tif. GEE-independent: reads aois/governorates.geojson. Robust
    to the fact that GEE/geedim export fills out-of-polygon pixels with 0 rather
    than nodata — the canonical clip is enforced HERE with rasterize.
    """
    import numpy as np
    import rasterio
    from rasterio.merge import merge
    from rasterio.features import geometry_mask
    import geopandas as gpd

    tmp_dir = AOIS_DIR / "_mask_tiles"
    gov = gpd.read_file(GOV_PATH).to_crs(CRS)
    geom_by_id = {r["aoi_id"]: r.geometry for _, r in gov.iterrows()}

    parts, stats = [], {}
    for a in AOIS:
        tile = tmp_dir / f"{a['aoi_id']}.tif"
        clipped = tmp_dir / f"{a['aoi_id']}_clip.tif"
        with rasterio.open(tile) as ds:
            arr = ds.read(1)
            inside = geometry_mask([geom_by_id[a["aoi_id"]].__geo_interface__],
                                   out_shape=arr.shape, transform=ds.transform, invert=True)
            arr = np.where(inside, arr, NODATA).astype("uint8")  # outside polygon -> nodata
            vals, counts = np.unique(arr[arr != NODATA], return_counts=True)
            stats[a["aoi_id"]] = {int(v): int(c) for v, c in zip(vals, counts)}
            prof = ds.profile
        prof.update(nodata=NODATA, dtype="uint8", compress="deflate", predictor=2, tiled=True)
        with rasterio.open(clipped, "w", **prof) as dst:
            dst.write(arr, 1)
        parts.append(clipped)

    srcs = [rasterio.open(p) for p in parts]
    mosaic, transform = merge(srcs, nodata=NODATA)
    profile = srcs[0].profile
    profile.update(height=mosaic.shape[1], width=mosaic.shape[2],
                   transform=transform, nodata=NODATA, count=1,
                   dtype="uint8", compress="deflate", predictor=2, tiled=True)
    for s in srcs:
        s.close()
    with rasterio.open(MASK_PATH, "w", **profile) as dst:
        dst.write(mosaic[0], 1)
        dst.update_tags(
            cropland_rule="value in {1,2,3} = cropland (union); 3 = both agree (intersection)",
            classes="0=neither 1=worldcover_only 2=dynamicworld_only 3=both 255=outside_aoi",
            sources="ESA/WorldCover/v200 (cls40) ; GOOGLE/DYNAMICWORLD/V1 crops mean>0.35",
            crs=CRS, scale_m=str(SCALE), reference_year=WC_YEAR)
    print(f"  -> {MASK_PATH}  shape={mosaic.shape[1]}x{mosaic.shape[2]}")
    return stats


def main():
    import ee
    initialize()
    print("== governorates ==")
    geoms = build_governorates(ee)
    print("== cropland mask ==")
    stats = build_cropland_mask(ee, geoms)
    (AOIS_DIR / "_mask_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("done. per-AOI class pixel counts written to aois/_mask_stats.json")


if __name__ == "__main__":
    main()
