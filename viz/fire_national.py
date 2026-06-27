"""National fire-damage maps (Pipeline B, docs/STRUCTURE.md §4).

Three figures over the 2026 fire re-run:
  * ``fire_choropleth_2026``        — burned cropland (ha) per governorate;
  * ``fire_hotspots_2026``          — VIIRS active-fire detections, by FRP;
  * ``fire_severity_breakdown_2026``— stacked burned-ha per governorate by dNBR
                                       severity.

Reads ONLY the shared damage schema (``outputs/tables/fire_damage.csv``) and the
cached VIIRS hotspot tables (``outputs/fire_hotspots/*_2026_viirs.csv``) — never a
pipeline's internal rasters (cross-reference discipline). Boundaries come from the
canonical AOI GeoJSON via :mod:`viz.maps`, so these match the report choropleth
exactly with no geopandas in the render env.

These are exploratory/diagnostic figures over the **unvalidated** re-run output;
they are NOT the gated report figures (those consume validated records only,
docs/STRUCTURE.md §6). The caveat strip says so on every figure.

Run:  PYTHONPATH=. python viz/fire_national.py
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path

from viz import maps

ROOT = Path(__file__).resolve().parent.parent
FIRE_CSV = ROOT / "outputs" / "tables" / "fire_damage.csv"
HOTSPOT_DIR = ROOT / "outputs" / "fire_hotspots"

# The 2026 re-run window (active-fire + S2 post-fire composite). Used in titles.
WINDOW = "2026-05-01 / 2026-06-27"

# Fire dNBR severity ramp (low→high), YlOrRd family so it reads in greyscale and
# shares the choropleth's hue.
SEVERITY_ORDER = ("low", "moderate_low", "moderate_high", "high")
SEVERITY_COLORS = {
    "low": "#fed976",
    "moderate_low": "#fd8d3c",
    "moderate_high": "#e31a1c",
    "high": "#800026",
}
SEVERITY_LABEL = {
    "low": "Low", "moderate_low": "Mod-low",
    "moderate_high": "Mod-high", "high": "High",
}

CAVEAT = (
    "UNVALIDATED / exploratory — VIIRS 375 m NRT + S2 dNBR, not human-validated "
    "(Tier-2 gate). Window clipped to live NRT coverage; late-season tail "
    "unobserved, so figures are lower bounds. Descriptive only."
)


# --- data loaders -----------------------------------------------------------

def damage_by_aoi(csv_path: Path = FIRE_CSV) -> dict[str, float]:
    """Total damaged_cropland_ha per AOI (summed over severity), from the schema CSV."""
    from schema.damage_schema import read_csv

    out: dict[str, float] = defaultdict(float)
    for rec in read_csv(csv_path):
        out[rec.aoi_id] += rec.damaged_cropland_ha
    return dict(out)


def damage_by_severity(csv_path: Path = FIRE_CSV) -> dict[str, dict[str, float]]:
    """``{aoi_id: {severity_class: ha}}`` from the schema CSV (damage classes only)."""
    from schema.damage_schema import read_csv

    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for rec in read_csv(csv_path):
        out[rec.aoi_id][rec.severity_class] += rec.damaged_cropland_ha
    return {a: dict(s) for a, s in out.items()}


def load_hotspots(hotspot_dir: Path = HOTSPOT_DIR, *, pattern: str = "*_2026_viirs.csv"):
    """Return ``(points, frp)`` — points = ``[(lon, lat), ...]``, frp = ``[MW, ...]``."""
    points: list[tuple[float, float]] = []
    frp: list[float] = []
    for p in sorted(Path(hotspot_dir).glob(pattern)):
        txt = p.read_text(encoding="utf-8").strip()
        if not txt:
            continue
        for r in csv.DictReader(io.StringIO(txt)):
            try:
                lon, lat = float(r["longitude"]), float(r["latitude"])
            except (KeyError, ValueError):
                continue
            try:
                f = float(r.get("frp") or 0.0)
            except ValueError:
                f = 0.0
            points.append((lon, lat))
            frp.append(f)
    return points, frp


def _gov_names() -> dict[str, str]:
    import json

    fc = json.loads(maps.AOIS_GEOJSON.read_text(encoding="utf-8"))
    return {f["properties"]["aoi_id"]: f["properties"].get("name", f["properties"]["aoi_id"])
            for f in fc["features"]}


# --- figures ----------------------------------------------------------------

def choropleth_figure(values: dict[str, float] | None = None):
    """Standalone burned-cropland choropleth (full resolution)."""
    from viz.style import caveat_footer

    values = damage_by_aoi() if values is None else values
    nat = sum(values.values())
    fig = maps.choropleth(
        values,
        title=("Syria 2026 cropland fires — burned cropland by governorate\n"
               f"{WINDOW}  ·  ~{nat:,.0f} ha across {len(values)} governorates"),
        cbar_label="Damaged cropland (ha, union)",
        cmap="YlOrRd",
        value_fmt="{:,.0f} ha",
        figsize=(10, 9),
    )
    caveat_footer(fig, CAVEAT)
    return fig


def hotspots_figure():
    """Standalone VIIRS hotspot map (points coloured by FRP), full resolution."""
    from viz.style import caveat_footer

    points, frp = load_hotspots()
    fig = maps.choropleth(
        {},  # outlines only — the hotspots carry the signal
        title=(f"Syria 2026 — VIIRS active-fire detections  (n = {len(points):,})\n"
               f"{WINDOW}"),
        cbar_label="",
        figsize=(10, 9),
        points=points,
        point_values=frp,
        point_cmap="inferno",
        point_size=4.0,
        point_cbar_label="Fire radiative power (MW, log)",
    )
    caveat_footer(fig, CAVEAT)
    return fig


def severity_breakdown_figure():
    """Horizontal stacked bars: burned cropland (ha) per governorate by dNBR severity."""
    import matplotlib.pyplot as plt

    from viz.style import apply_theme, caveat_footer

    apply_theme()
    by_sev = damage_by_severity()
    totals = {a: sum(s.values()) for a, s in by_sev.items()}
    order = sorted(totals, key=totals.get)  # ascending → largest bar on top
    names = _gov_names()

    fig, ax = plt.subplots(figsize=(10, 7))
    rows = [names[a] for a in order]
    left = {a: 0.0 for a in order}
    for sev in SEVERITY_ORDER:
        widths = [by_sev[a].get(sev, 0.0) for a in order]
        ax.barh(rows, widths, left=[left[a] for a in order],
                color=SEVERITY_COLORS[sev], label=SEVERITY_LABEL[sev],
                edgecolor="white", linewidth=0.4)
        for a, w in zip(order, widths):
            left[a] += w
    for a in order:
        ax.text(totals[a], names[a], f"  {totals[a]:,.0f}",
                va="center", ha="left", fontsize=8, color="#333333")
    ax.set_xlabel("Burned cropland (ha, union)")
    ax.set_title(f"Syria 2026 cropland fires — severity by governorate  ·  {WINDOW}")
    ax.margins(x=0.13)
    ax.legend(title="dNBR severity", loc="lower right", frameon=True, fontsize=8)
    caveat_footer(fig, CAVEAT)
    return fig


def render_all() -> list[Path]:
    """Render all three figures to outputs/figures/ and return their paths."""
    from viz.style import save_figure

    return [
        save_figure(choropleth_figure(), "fire_choropleth_2026"),
        save_figure(hotspots_figure(), "fire_hotspots_2026"),
        save_figure(severity_breakdown_figure(), "fire_severity_breakdown_2026"),
    ]


if __name__ == "__main__":
    for path in render_all():
        print(f"wrote {path}")
