"""Build aois/control_areas.geojson — RQ3 INDICATIVE overlay only (DEC-005).

HARD FRAMING CONSTRAINT (DEC-005, docs/PRODUCT.md §5/§9, CLAUDE.md): this layer
is DESCRIPTIVE ONLY. It maps where 2026 cropland damage falls relative to
*indicative* government-controlled vs former-AANES areas. It MUST NEVER support a
claim that either administration fared better or worse. Boundaries are contested
and treated as indicative; they are NOT an authoritative control map.

Provenance of the indicative labels: the well-documented 2017–2024 control
geography (SDF / AANES northeast-of-Euphrates; government southwest), with the
Euphrates river used as a SCHEMATIC proxy for the Deir ez-Zor dividing line. This
is coarse on purpose. Post-Dec-2024 (fall of the Assad government) control is
fluid; "former AANES" reflects that. A dated, authoritative control map should
replace this before RQ3 (S11) if a finer overlay is wanted — flagged for human.

Reads aois/governorates.geojson (no GEE). Run:
    conda run -n f_f python aois/build_control_areas.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString
from shapely.ops import split, unary_union

REPO = Path(__file__).resolve().parent.parent
AOIS_DIR = REPO / "aois"
GOV_PATH = AOIS_DIR / "governorates.geojson"
OUT_PATH = AOIS_DIR / "control_areas.geojson"

# Coarse Euphrates course (lon, lat), NW->SE, extended past the AOI bbox so it
# cleanly splits the Deir ez-Zor polygon. A schematic proxy, NOT a survey line.
EUPHRATES = LineString([
    (37.5, 36.9), (38.5, 35.9), (39.0, 35.95), (40.14, 35.34),
    (40.45, 35.02), (40.92, 34.45), (41.6, 34.0),
])

# Indicative predominant administration per AOI (2017–2024 geography; contested).
INDICATIVE = {
    "latakia": "government",
    "hasakah": "former_AANES",
    "raqqa": "former_AANES",
    # deir_ez_zor handled specially: split by the Euphrates proxy.
}

CAVEAT = ("INDICATIVE / CONTESTED — descriptive overlay only (DEC-005). NOT an "
          "authoritative control map. No differential or causal claim may be "
          "drawn from this layer. Euphrates used as a schematic proxy line.")


def _feature(geom, aoi_id, name, admin, basis):
    return {
        "type": "Feature",
        "properties": {
            "aoi_id": aoi_id, "name": name,
            "indicative_admin": admin, "indicative": True,
            "basis": basis, "caveat": CAVEAT,
        },
        "geometry": json.loads(gpd.GeoSeries([geom], crs=4326).to_json())["features"][0]["geometry"],
    }


def main():
    gov = gpd.read_file(GOV_PATH)
    feats = []
    for _, row in gov.iterrows():
        aoi_id, name, geom = row["aoi_id"], row["name"], row.geometry
        if aoi_id == "deir_ez_zor":
            pieces = list(split(geom, EUPHRATES).geoms)
            # classify each piece by centroid side: NE of river -> former AANES.
            ne, sw = [], []
            for p in pieces:
                c = p.centroid
                # crude side test: north-east bank if centroid is left of the
                # NW->SE line (higher lat for a given lon). Use signed distance
                # via the river's local bearing midpoint.
                (ne if _is_northeast(c) else sw).append(p)
            if ne:
                feats.append(_feature(unary_union(ne), aoi_id, name, "former_AANES",
                                      "Deir ez-Zor NE-of-Euphrates (schematic proxy)"))
            if sw:
                feats.append(_feature(unary_union(sw), aoi_id, name, "government",
                                      "Deir ez-Zor SW-of-Euphrates (schematic proxy)"))
        else:
            feats.append(_feature(geom, aoi_id, name, INDICATIVE[aoi_id],
                                  "2017-2024 predominant control geography (indicative)"))

    fc = {"type": "FeatureCollection",
          "name": "syria_2026_control_areas_indicative",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
          "_caveat": CAVEAT,
          "features": feats}
    OUT_PATH.write_text(json.dumps(fc, indent=2), encoding="utf-8")
    print(f"-> {OUT_PATH}  ({len(feats)} indicative features)")
    for f in feats:
        p = f["properties"]
        print(f"   {p['aoi_id']:12s} {p['indicative_admin']:13s} {p['basis']}")


def _is_northeast(point) -> bool:
    """True if point is on the NE (left) side of the NW->SE Euphrates line."""
    # Interpolate the river latitude at the point's longitude and compare.
    xs = [c[0] for c in EUPHRATES.coords]
    ys = [c[1] for c in EUPHRATES.coords]
    lon = min(max(point.x, min(xs)), max(xs))
    # piecewise-linear river latitude at this longitude
    river_lat = None
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if (x0 <= lon <= x1) or (x1 <= lon <= x0):
            t = 0 if x1 == x0 else (lon - x0) / (x1 - x0)
            river_lat = ys[i] + t * (ys[i + 1] - ys[i])
            break
    if river_lat is None:
        river_lat = ys[-1]
    return point.y >= river_lat  # north of the river course -> NE bank


if __name__ == "__main__":
    main()
