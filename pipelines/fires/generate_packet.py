"""Tier-2 validation packet for Pipeline B fires (docs/STRUCTURE.md §6, DEC-007).

Renders, per fire AOI/window, a two-panel figure the HUMAN compares against named
ground truth before flipping any ``validation_status``:
  * LEFT  — context: VIIRS hotspots (cyan rings) over a post-fire Sentinel-2
            true-colour background, whole hotspot extent.
  * RIGHT — zoom on the densest hotspot cluster, with the dNBR burn-severity
            classification (DEC-009 palette) masked to fire-confirmed cropland
            (DEC-031 + DEC-015 union) — legible enough to judge scar realism.

The 2025 Latakia panel is the EMSR811 anchor — the human overlays the Copernicus
EMS EMSR811 delineation (downloaded from the EMS portal) to validate the *method*;
its scar is shown FULL (not cropland-confined) because EMSR811 burned forest.
No agent flips validation_status; this script only assembles the surface.

Run:  PYTHONPATH=. python pipelines/fires/generate_packet.py
"""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path

import requests

from clients import gee_auth
from pipelines.fires import active_fire as af
from pipelines.fires import burn_severity as bs
from pipelines.fires.build_fires import JOBS, ROOT

OUT = ROOT / "outputs" / "fire_validation"
_SEV_PALETTE = ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c"]  # low→high
_SEV_LABELS = ["low", "moderate_low", "moderate_high", "high"]


def _post_rgb(geom, post):
    """Cloud-masked S2 true-colour median over the post window."""
    import ee

    def _mask(img):
        scl = img.select("SCL")
        good = scl.neq(3)
        for v in (8, 9, 10, 11):
            good = good.And(scl.neq(v))
        return img.updateMask(good)

    col = (ee.ImageCollection(bs._S2)
           .filterBounds(geom).filterDate(*post)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60)).map(_mask))
    return col.select(["B4", "B3", "B2"]).median()


def _thumb(image, region, dimensions=1100):
    """getThumbURL → numpy RGB array (downloaded PNG)."""
    import numpy as np
    from PIL import Image

    url = image.getThumbURL({"region": region, "dimensions": dimensions, "format": "png"})
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    return np.array(Image.open(io.BytesIO(r.content)).convert("RGB"))


def _densest_bbox(rows, *, cell_deg=0.05, pad_deg=0.06):
    """BBox around the densest hotspot cluster (coarse grid vote) → zoom window."""
    gdf_rows = af._clean(rows)
    cells = Counter((round(r["longitude"] / cell_deg), round(r["latitude"] / cell_deg))
                    for r in gdf_rows)
    (cx, cy), _ = cells.most_common(1)[0]
    lon0, lat0 = cx * cell_deg, cy * cell_deg
    return (lon0 - pad_deg, lat0 - pad_deg, lon0 + pad_deg, lat0 + pad_deg)


def _draw(ax, arr, extent, gdf, n, *, title):
    from matplotlib.patches import Patch
    w, s, e, n_ = extent
    ax.imshow(arr, extent=[w, e, s, n_], origin="upper")
    # Rings (not filled) so the severity scar shows through.
    ax.scatter(gdf.geometry.x, gdf.geometry.y, s=14, facecolors="none",
               edgecolors="cyan", linewidths=0.6, alpha=0.8)
    ax.set_xlim(w, e); ax.set_ylim(s, n_)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("lon"); ax.set_ylabel("lat")


def render():
    import ee
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    gee_auth.initialize()
    OUT.mkdir(parents=True, exist_ok=True)
    g = json.loads((ROOT / "aois" / "governorates.geojson").read_text())
    geoms = {f["properties"]["aoi_id"]: ee.Geometry(f["geometry"]) for f in g["features"]}
    union, _inter = bs.cropland_masks()

    for aoi, label, date_str, sources, pre, post, is_study in JOBS:
        rows = af.fetch(aoi, *date_str.split("/"), sources=sources)
        summ = af.summary(rows)
        if summ["n"] == 0:
            print(f"  {aoi} [{label}]: 0 hotspots — skipping panel")
            continue
        gdf = af.to_gdf(rows)

        near = af.near_fire_mask(rows)
        dnbr = bs.dnbr_image(geoms[aoi], pre, post)
        # Study AOIs: cropland-confined scar (what the damage records count).
        # EMSR811 anchor: FULL fire-confirmed scar (it burned forest, not cropland).
        sev = bs.severity_class_image(dnbr).updateMask(near)
        if is_study:
            sev = sev.updateMask(union)
        sev_vis = sev.visualize(min=1, max=4, palette=_SEV_PALETTE)

        ctx = af.bbox_lonlat(rows, pad_deg=0.05)
        zoom = _densest_bbox(rows)
        try:
            ctx_arr = _thumb(_post_rgb(geoms[aoi], post).visualize(min=200, max=3000),
                             ee.Geometry.Rectangle(list(ctx)))
            zoom_bg = _post_rgb(geoms[aoi], post).visualize(min=200, max=3000)
            zoom_arr = _thumb(zoom_bg.blend(sev_vis), ee.Geometry.Rectangle(list(zoom)))
        except Exception as ex:  # noqa: BLE001
            print(f"  {aoi} [{label}]: thumbnail failed ({ex}) — skipping panel")
            continue

        kind = "STUDY (2026)" if is_study else "EMSR811 ANCHOR (2025 — method validation)"
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 7.5))
        _draw(axL, ctx_arr, ctx, gdf, summ["n"],
              title=f"context — all VIIRS hotspots (n={summ['n']})")
        zg = gdf.cx[zoom[0]:zoom[2], zoom[1]:zoom[3]]
        _draw(axR, zoom_arr, zoom, zg, len(zg),
              title=f"zoom — densest cluster + dNBR severity (n={len(zg)} here)")
        legend = [Patch(facecolor=c, label=l) for c, l in zip(_SEV_PALETTE, _SEV_LABELS)]
        legend.append(Patch(edgecolor="cyan", facecolor="none", label="VIIRS hotspot"))
        axR.legend(handles=legend, loc="lower left", fontsize=8, framealpha=0.9)

        fig.suptitle(f"{aoi.upper()} [{label}] — {kind}   |   {date_str}   |   "
                     f"dates={summ['dates']}  frp_max={summ['frp_max']}", fontsize=11)
        cap = ("UNVALIDATED — Tier-2 human gate (§6). dNBR severity (DEC-009) on "
               "fire-confirmed cropland (DEC-031 near-fire ∩ DEC-015 union). "
               "Scars should co-locate with hotspots; judge realism vs known fire geography.")
        if not is_study:
            cap = ("EMSR811 anchor — overlay Copernicus EMS EMSR811 delineation to "
                   "validate the dNBR method (scar shown FULL, not cropland-confined). "
                   "2025 = baseline/context (DEC-001), not a study damage record.")
        fig.text(0.5, 0.005, cap, ha="center", fontsize=8, wrap=True)
        out = OUT / f"{aoi}_{label}_validation.png"
        fig.savefig(out, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"  wrote {out}  (zoom bbox {tuple(round(v,3) for v in zoom)})")


if __name__ == "__main__":
    render()
