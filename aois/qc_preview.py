"""QC previews for the human cropland-mask review gate (S3 completion criterion 4).

Renders, per AOI, the reconciled cropland mask (by source-agreement class) over a
basemap, plus a summary table of cropland hectares (union vs intersection) and the
DW-vs-WorldCover disagreement share. This is the SURFACE the human reviews before
any pipeline (S6/S7) consumes the mask (§6, DEC-007) — agents cannot self-certify.

Run after aois/build_aois.py:
    conda run -n f_f python aois/qc_preview.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
import geopandas as gpd

REPO = Path(__file__).resolve().parent.parent
AOIS_DIR = REPO / "aois"
OUT_DIR = REPO / "outputs" / "aoi_qc"
PIX_HA = 0.09  # 30 m pixel = 900 m2 = 0.09 ha

# class -> (label, color)
CLASSES = {
    0: ("non-cropland", "#eeeee4"),
    1: ("WorldCover only", "#e8a33d"),
    2: ("Dynamic World only", "#3d7be8"),
    3: ("both agree", "#2e7d32"),
}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gov = gpd.read_file(AOIS_DIR / "governorates.geojson").to_crs("EPSG:32637")
    cmap = ListedColormap([CLASSES[i][1] for i in range(4)])
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)

    summary = {}
    with rasterio.open(AOIS_DIR / "cropland_mask.tif") as ds:
        for _, row in gov.iterrows():
            aoi_id, name = row["aoi_id"], row["name"]
            minx, miny, maxx, maxy = row.geometry.bounds
            win = from_bounds(minx, miny, maxx, maxy, ds.transform)
            arr = ds.read(1, window=win)
            wt = ds.window_transform(win)
            ext = rasterio.windows.bounds(win, ds.transform)
            # mask to THIS AOI polygon so neighbouring AOIs in the bbox window
            # are excluded from both the count and the display.
            inside = geometry_mask([row.geometry.__geo_interface__],
                                   out_shape=arr.shape, transform=wt, invert=True)
            disp = np.where(inside & (arr != ds.nodata), arr, np.nan)

            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(disp, cmap=cmap, norm=norm,
                      extent=[ext[0], ext[2], ext[1], ext[3]], interpolation="nearest")
            gpd.GeoSeries([row.geometry], crs="EPSG:32637").boundary.plot(
                ax=ax, color="black", linewidth=0.8)
            counts = {c: int(((arr == c) & inside).sum()) for c in range(4)}
            union_ha = (counts[1] + counts[2] + counts[3]) * PIX_HA
            inter_ha = counts[3] * PIX_HA
            disagree = 0.0 if union_ha == 0 else 1 - inter_ha / union_ha
            ax.set_title(f"{name} — cropland mask (30 m, EPSG:32637)\n"
                         f"union {union_ha:,.0f} ha · intersection {inter_ha:,.0f} ha · "
                         f"DW/WC disagreement {disagree:.0%}")
            ax.legend(handles=[Patch(facecolor=CLASSES[i][1], edgecolor="k", label=CLASSES[i][0])
                               for i in range(4)], loc="lower left", fontsize=8)
            ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
            fig.tight_layout()
            fig.savefig(OUT_DIR / f"{aoi_id}_cropland_mask.png", dpi=110)
            plt.close(fig)
            summary[aoi_id] = {"name": name, "union_ha": round(union_ha, 1),
                               "intersection_ha": round(inter_ha, 1),
                               "disagreement_share": round(disagree, 3),
                               "class_pixels": counts}
            print(f"  {name:12s} union={union_ha:9,.0f} ha  inter={inter_ha:9,.0f} ha  "
                  f"disagree={disagree:.0%}")

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"-> previews + summary in {OUT_DIR}")


if __name__ == "__main__":
    main()
