"""Lightweight choropleth maps from the canonical AOI GeoJSON (DEC-008).

The report's render env is deliberately geo-stack-free (report/requirements.txt:
pandas + matplotlib + seaborn + jupyter only). So this module draws governorate
polygons straight from ``aois/governorates.geojson`` with the standard library's
``json`` plus matplotlib patches — no geopandas / shapely / GDAL. That keeps the
GitHub Pages render light while still giving the study the one thing it was missing:
a map of *where* the damage falls.

The maps make no comparative or causal claim — a plain per-governorate value map is
descriptive and safe (the DEC-005 concern is the *control-zone* overlay, not a
governorate-loss map). Caveats still ride the figure via ``caveat_footer``.

All geometry math (centroids, aspect) is done by hand so nothing here needs shapely.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

# Canonical AOIs (docs/STRUCTURE.md §3.1) — every module reads these, none redefine.
AOIS_GEOJSON = Path(__file__).resolve().parent.parent / "aois" / "governorates.geojson"

# Governorates that carry no study damage (verified-excluded / outside scope) are
# drawn for geographic context in this neutral grey, never colour-coded.
_NO_DATA_COLOR = "#e8e8e8"


def _polygons(geometry: dict) -> list[list[tuple[float, float]]]:
    """Return exterior rings as lists of (lon, lat) tuples.

    Handles Polygon and MultiPolygon; holes (interior rings) are dropped — the
    governorate boundaries have none that matter at report scale, and matplotlib's
    simple ``Polygon`` patch fills the exterior, which is what a choropleth needs.
    """
    gtype = geometry["type"]
    rings: list[list[tuple[float, float]]] = []
    if gtype == "Polygon":
        rings.append([(x, y) for x, y in geometry["coordinates"][0]])
    elif gtype == "MultiPolygon":
        for poly in geometry["coordinates"]:
            rings.append([(x, y) for x, y in poly[0]])
    return rings


def _rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Ramer–Douglas–Peucker line simplification (iterative, no recursion limit).

    Cuts the vertex count of the detailed GAUL boundaries by ~20–50× at report
    scale, so the choropleth stays a small, crisp SVG instead of an 0.7 MB one,
    using only the standard library (CI has no shapely). ``eps`` is in degrees.
    """
    n = len(points)
    if n < 3:
        return points[:]
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i0, i1 = stack.pop()
        ax, ay = points[i0]
        bx, by = points[i1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        dmax, idx = -1.0, -1
        for i in range(i0 + 1, i1):
            px, py = points[i]
            if seg2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                # perpendicular distance from point to the segment line
                d = abs(dy * px - dx * py + bx * ay - by * ax) / math.sqrt(seg2)
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps and idx != -1:
            keep[idx] = True
            stack.append((i0, idx))
            stack.append((idx, i1))
    return [points[i] for i in range(n) if keep[i]]


def _ring_centroid_area(ring: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Polygon centroid and signed area via the shoelace formula (no shapely)."""
    a = cx = cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-12:  # degenerate — fall back to vertex mean
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys), 0.0
    return cx / (6 * a), cy / (6 * a), abs(a)


def _label_point(rings: list[list[tuple[float, float]]]) -> tuple[float, float, float]:
    """Centroid and area (deg²) of the largest ring — where to drop the label."""
    best, best_area = (0.0, 0.0), -1.0
    for ring in rings:
        cx, cy, area = _ring_centroid_area(ring)
        if area > best_area:
            best, best_area = (cx, cy), area
    return best[0], best[1], best_area


# A no-data polygon smaller than this (deg²) is left unlabelled so its name does not
# collide with the larger governorate it sits inside (e.g. Damascus City in Rural
# Damascus). In-scope AOIs are always labelled.
_MIN_NODATA_LABEL_AREA = 0.04


def choropleth(
    values: Mapping[str, float],
    *,
    title: str,
    cbar_label: str,
    cmap: str = "YlOrRd",
    value_fmt: str = "{:.1f}",
    label_names: bool = True,
    geojson_path: Path | None = None,
    figsize: tuple[float, float] = (8.5, 7.5),
    simplify_deg: float = 0.008,
    points: Iterable[tuple[float, float]] | None = None,
    point_values: Sequence[float] | None = None,
    point_cmap: str = "inferno",
    point_size: float = 3.0,
    point_alpha: float = 0.55,
    point_color: str = "#333333",
    point_cbar_label: str | None = None,
):
    """Draw a governorate choropleth shaded by ``values`` (keyed by ``aoi_id``).

    Parameters
    ----------
    values
        ``{aoi_id: value}``. AOIs absent from the mapping are drawn in the neutral
        no-data grey (e.g. verified-excluded Latakia / Damascus City). Pass an
        empty mapping to draw outlines only (e.g. a pure hotspot map) — the value
        colour-bar is then suppressed.
    title, cbar_label
        Plot title and colour-bar label.
    cmap
        A perceptually-uniform sequential colormap (default ``YlOrRd`` — light→dark
        reads as low→high loss and survives greyscale / common colour-blindness).
    value_fmt
        Format applied to the per-governorate value annotation.
    points
        Optional ``(lon, lat)`` pairs scattered above the choropleth — e.g. VIIRS
        active-fire hotspots. ``point_values`` (same length, e.g. FRP) colours them
        on a log scale with its own colour-bar; otherwise they use ``point_color``.

    Returns the matplotlib ``Figure``. The caller stamps caveats via
    ``caveat_footer`` and Quarto embeds it; nothing is written to disk here.
    """
    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import LogNorm, Normalize
    from matplotlib.patches import Polygon as MplPolygon

    path = geojson_path or AOIS_GEOJSON
    features = json.loads(Path(path).read_text(encoding="utf-8"))["features"]

    vmax = max(values.values()) if values else 1.0
    vmin = 0.0
    norm = Normalize(vmin=vmin, vmax=vmax)
    cmapper = ScalarMappable(norm=norm, cmap=cmap)

    fig, ax = plt.subplots(figsize=figsize)
    all_lats: list[float] = []
    all_lons: list[float] = []

    for feat in features:
        aoi = feat["properties"]["aoi_id"]
        name = feat["properties"].get("name", aoi)
        rings = _polygons(feat["geometry"])
        if simplify_deg:
            rings = [r for r in (_rdp(r, simplify_deg) for r in rings) if len(r) >= 3]
        if not rings:
            continue
        has_val = aoi in values
        face = cmapper.to_rgba(values[aoi]) if has_val else _NO_DATA_COLOR
        for ring in rings:
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            all_lons.extend(xs)
            all_lats.extend(ys)
            ax.add_patch(
                MplPolygon(
                    ring, closed=True, facecolor=face, edgecolor="white",
                    linewidth=0.8, zorder=1,
                )
            )
        if label_names:
            lx, ly, larea = _label_point(rings)
            if not has_val and larea < _MIN_NODATA_LABEL_AREA:
                continue  # tiny no-data enclave — skip to avoid label collision
            txt = name if not has_val else f"{name}\n{value_fmt.format(values[aoi])}"
            # White halo keeps the label legible over any fill shade.
            ax.text(
                lx, ly, txt, ha="center", va="center", fontsize=7.5,
                zorder=3, color="#1a1a1a",
                path_effects=_halo(),
            )

    # Optional hotspot overlay (e.g. VIIRS active-fire points), drawn above the
    # choropleth. Colour-by-value (FRP) uses a log scale so a few high-power
    # detections don't wash out the rest.
    point_sc = None
    if points is not None:
        plons = [p[0] for p in points]
        plats = [p[1] for p in points]
        if point_values is not None:
            pvals = [max(float(v), 1e-3) for v in point_values]
            point_sc = ax.scatter(
                plons, plats, c=pvals, cmap=point_cmap,
                norm=LogNorm(vmin=1.0, vmax=max(max(pvals), 10.0)),
                s=point_size, alpha=point_alpha, linewidths=0, zorder=2,
            )
        else:
            ax.scatter(plons, plats, c=point_color, s=point_size,
                       alpha=point_alpha, linewidths=0, zorder=2)
        all_lons.extend(plons)
        all_lats.extend(plats)

    # Geographic aspect: 1 deg lon is shorter than 1 deg lat away from the equator.
    mean_lat = sum(all_lats) / len(all_lats)
    ax.set_aspect(1.0 / math.cos(math.radians(mean_lat)))
    ax.set_xlim(min(all_lons) - 0.2, max(all_lons) + 0.2)
    ax.set_ylim(min(all_lats) - 0.2, max(all_lats) + 0.2)
    ax.set_axis_off()
    ax.set_title(title)

    if values:  # suppress the value bar for an outlines-only / hotspot map
        cbar = fig.colorbar(cmapper, ax=ax, fraction=0.035, pad=0.02, shrink=0.7)
        cbar.set_label(cbar_label)
    if point_sc is not None:
        pcb = fig.colorbar(point_sc, ax=ax, fraction=0.035, pad=0.02, shrink=0.7)
        pcb.set_label(point_cbar_label or cbar_label)

    return fig


def _halo():
    """A thin white outline for map labels (import kept local to stay lazy)."""
    import matplotlib.patheffects as pe

    return [pe.withStroke(linewidth=2.0, foreground="white")]
