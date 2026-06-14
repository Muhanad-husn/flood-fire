"""RQ3 — descriptive control-area overlay (docs/PRODUCT.md §5 Secondary 3; W9).

DESCRIPTIVE ONLY (DEC-005, PRODUCT.md §5/§9, CLAUDE.md). This module maps WHERE the
2026 validated cropland damage falls relative to *indicative* control zones. It must
NEVER infer that either administration fared better or worse — no differential, no
causal claim. The module name `control_differential.py` is legacy; it computes no
differential. Boundaries are contested and treated as indicative only.

Hard constraints respected here:

  * Validated-only (§6). Reads only `is_consumable()` DamageRecords via the shared
    schema (§3.2) — never a pipeline's internal rasters (cross-reference discipline).
  * AOI granularity. The shared schema is per-AOI; it carries no sub-AOI geometry, and
    an RQ analysis may not read the flood/fire rasters to manufacture one. So an AOI
    that SPANS two indicative zones (Deir ez-Zor, split NE/SW by a schematic Euphrates
    proxy) is reported as spanning both, UNAPPORTIONED — we do not fabricate a split.
  * Scope = the AOIs where indicative control zones are defined. `aois/control_areas.geojson`
    covers the four original AOIs (Deir ez-Zor, Raqqa, Hasakah, Latakia). The national
    fire-only governorates (S13/DEC-037) are OUTSIDE this overlay's geographic scope —
    control geometry was never drawn there, and drawing contested boundaries for nine
    more governorates to force an overlay would itself be the kind of authoritative
    control-map claim DEC-005 forbids. Their damage is listed separately as
    "outside indicative control-area coverage", with no zone assigned.

Per-AOI headline damaged hectares reuse the food-security layer's schema-level
aggregations (union headline, flood peak-date no-double-count) so the same number is
reported everywhere — those helpers are pure functions over DamageRecords, not pipeline
internals.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from schema.damage_schema import DamageRecord, read_csv
from food_security.impact_layer import (
    FLOOD_CSV,
    FIRE_CSV,
    aggregate_floods,
    aggregate_fires,
    gate_records,
)

# --- paths (docs/STRUCTURE.md §2) ---------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROL_AREAS = REPO_ROOT / "aois" / "control_areas.geojson"
OUT_DIR = REPO_ROOT / "outputs" / "analysis" / "rq3_control_overlay"

_OUT_OF_SCOPE = "outside indicative control-area coverage"

# The shared, prominent contested/indicative caveat carried on EVERY artifact (DEC-005).
INDICATIVE_CAVEAT = (
    "INDICATIVE / CONTESTED boundaries — descriptive overlay only (DEC-005). NOT an "
    "authoritative control map. No differential or causal claim may be drawn: this layer "
    "does not state or imply that either administration fared better or worse. The "
    "Euphrates is used as a schematic proxy line; control geography is the indicative "
    "2017-2024 predominant pattern."
)


# --- indicative control zones (read from the geojson) -------------------------

def load_zone_map(path: Path = CONTROL_AREAS) -> dict[str, tuple[str, ...]]:
    """aoi_id -> sorted tuple of the indicative_admin labels it spans.

    An AOI mapped to a single label (Raqqa/Hasakah -> former_AANES, Latakia ->
    government) sits wholly within one indicative zone; an AOI mapped to >1 label
    (Deir ez-Zor -> former_AANES + government) SPANS zones and is not apportioned.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    spans: dict[str, set[str]] = defaultdict(set)
    for feat in data["features"]:
        p = feat["properties"]
        spans[p["aoi_id"]].add(p["indicative_admin"])
    return {aoi: tuple(sorted(labels)) for aoi, labels in spans.items()}


def zone_label(labels: Sequence[str]) -> str:
    """A descriptive, comparison-free label for the indicative zone(s) an AOI spans."""
    if len(labels) == 1:
        return f"{labels[0]} (indicative)"
    return "spans " + " + ".join(labels) + " (indicative; unapportioned)"


# --- the descriptive overlay (schema-only, AOI-granular) ----------------------

@dataclass
class OverlayRow:
    aoi_id: str
    phenomenon: str                 # "flood" | "fire"
    damaged_ha_headline_union: float
    indicative_zone: str            # descriptive label; or the out-of-scope tag
    in_scope: bool                  # within the indicative control-area geography?


def build_overlay(
    records: Iterable[DamageRecord],
    zone_map: dict[str, tuple[str, ...]] | None = None,
) -> list[OverlayRow]:
    """Per-AOI/-phenomenon headline damaged ha, tagged with its indicative zone.

    Descriptive only. AOIs covered by `control_areas.geojson` get their indicative
    zone label (single or spanning); AOIs outside that coverage (the national fire
    govs) are tagged "outside indicative control-area coverage" with no zone claim.
    """
    if zone_map is None:
        zone_map = load_zone_map()
    recs = list(records)
    flood_dmg = aggregate_floods(recs)
    fire_dmg = aggregate_fires(recs)

    rows: list[OverlayRow] = []
    for dmg_map, phenom in ((flood_dmg, "flood"), (fire_dmg, "fire")):
        for aoi, d in sorted(dmg_map.items()):
            if d.ha_headline <= 0:
                continue
            labels = zone_map.get(aoi)
            if labels is None:
                rows.append(OverlayRow(aoi, phenom, d.ha_headline, _OUT_OF_SCOPE, False))
            else:
                rows.append(OverlayRow(aoi, phenom, d.ha_headline, zone_label(labels), True))
    return rows


def summarise_by_zone(rows: Sequence[OverlayRow]) -> list[dict[str, object]]:
    """Total validated damaged ha grouped by indicative zone label (descriptive).

    A flat tabulation of where damage is located. Makes NO comparison between zones.
    """
    by_zone: dict[str, dict[str, float]] = defaultdict(
        lambda: {"flood_ha": 0.0, "fire_ha": 0.0}
    )
    aois_in_zone: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        by_zone[r.indicative_zone][f"{r.phenomenon}_ha"] += r.damaged_ha_headline_union
        aois_in_zone[r.indicative_zone].add(r.aoi_id)
    out: list[dict[str, object]] = []
    for zone in sorted(by_zone):
        z = by_zone[zone]
        out.append({
            "indicative_zone": zone,
            "aois": ", ".join(sorted(aois_in_zone[zone])),
            "flood_ha_headline_union": round(z["flood_ha"], 2),
            "fire_ha_headline_union": round(z["fire_ha"], 2),
            "total_ha_headline_union": round(z["flood_ha"] + z["fire_ha"], 2),
        })
    return out


# --- outputs: table + finding + map -------------------------------------------

_OVERLAY_FIELDS = (
    "aoi_id", "phenomenon", "damaged_ha_headline_union", "indicative_zone", "in_scope",
)
_ZONE_FIELDS = (
    "indicative_zone", "aois",
    "flood_ha_headline_union", "fire_ha_headline_union", "total_ha_headline_union",
)


def write_tables(rows: Sequence[OverlayRow], out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    p_overlay = out_dir / "damage_by_aoi_zone.csv"
    with p_overlay.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_OVERLAY_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: getattr(r, k) for k in _OVERLAY_FIELDS})
    p_zone = out_dir / "damage_by_indicative_zone.csv"
    with p_zone.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_ZONE_FIELDS)
        w.writeheader()
        for row in summarise_by_zone(rows):
            w.writerow(row)
    return p_overlay, p_zone


def write_finding(rows: Sequence[OverlayRow], out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zones = summarise_by_zone(rows)
    in_scope = [z for z in zones if z["indicative_zone"] != _OUT_OF_SCOPE]
    out_scope = [z for z in zones if z["indicative_zone"] == _OUT_OF_SCOPE]
    lines: list[str] = []
    lines.append("# RQ3 — descriptive damage-vs-control overlay (W9, DEC-005)\n")
    lines.append(f"\n> ⚠ **{INDICATIVE_CAVEAT}**\n")
    lines.append(
        "\n> ⚠ **First-half-2026 case study (DEC-039).** Damage figures cover floods "
        "Mar–Jun and fires May 1 – Jun 12 only; they are lower bounds on the full year.\n"
    )
    lines.append("\n## What this is (and is not)\n")
    lines.append(
        "- **Is:** a descriptive tabulation of *where* validated 2026 cropland damage "
        "falls relative to indicative control zones, at the shared schema's per-AOI "
        "granularity.\n"
    )
    lines.append(
        "- **Is not:** a comparison. Nothing here states or implies that damage was "
        "higher/lower, or response better/worse, under either indicative administration. "
        "The control geography is contested and indicative; the Euphrates split of Deir "
        "ez-Zor is a schematic proxy.\n"
    )
    lines.append("\n## Scope\n")
    lines.append(
        "- **In scope:** the four AOIs where indicative control zones are defined "
        "(`aois/control_areas.geojson`): Deir ez-Zor, Raqqa, Hasakah, Latakia.\n"
    )
    lines.append(
        "- **Out of scope:** the national fire-only governorates (S13/DEC-037) — control "
        "geometry was never drawn there, and extending contested boundaries to force an "
        "overlay would itself breach DEC-005. Their damage is listed separately, with no "
        "zone assigned.\n"
    )
    lines.append(
        "- **Deir ez-Zor spans two indicative zones** (former-AANES NE / government SW of "
        "the schematic Euphrates line). The per-AOI schema cannot apportion its hectares "
        "between them, and an RQ analysis may not read the flood/fire rasters to do so "
        "(cross-reference discipline). It is therefore reported as **spanning both, "
        "unapportioned** — deliberately, not as an omission.\n"
    )
    lines.append("\n## Descriptive tabulation — validated damaged cropland by indicative zone\n")
    lines.append("\n| Indicative zone | AOIs | Flood ha | Fire ha | Total ha |\n")
    lines.append("|---|---|---:|---:|---:|\n")
    for z in in_scope:
        lines.append(
            f"| {z['indicative_zone']} | {z['aois']} | {z['flood_ha_headline_union']:,.0f} | "
            f"{z['fire_ha_headline_union']:,.0f} | {z['total_ha_headline_union']:,.0f} |\n"
        )
    lines.append(
        "\n*Hectares are the union-cropland headline (DEC-015/DEC-032), flood figures the "
        "peak single event-date extent (no cross-date double-count, DEC-033). Listing "
        "side by side is descriptive co-location, not a comparison.*\n"
    )
    if out_scope:
        z = out_scope[0]
        lines.append("\n## Outside indicative control-area coverage (no zone assigned)\n")
        lines.append(
            f"- National fire-only governorates ({z['aois']}): "
            f"**{z['fire_ha_headline_union']:,.0f} ha** validated burned cropland, located "
            "outside the drawn indicative control geography. Reported for transparency; **no "
            "control zone is attributed.**\n"
        )
    lines.append("\n## Caveats (every artifact carries these)\n")
    lines.append(f"- {INDICATIVE_CAVEAT}\n")
    lines.append(
        "- Damaged hectares inherit the pipeline caveats: flood extent is open-water "
        "riverine inundation (DEC-023); burned cropland is VIIRS-confirmed dNBR, a "
        "conservative lower bound (DEC-031).\n"
    )
    lines.append(
        "- First-half-2026 scope: figures are lower bounds; the summer harvest/fire peak "
        "is unobserved (DEC-039).\n"
    )
    lines.append("\n## Outputs\n")
    lines.append("- `damage_by_aoi_zone.csv` — per AOI × phenomenon headline ha + its indicative zone.\n")
    lines.append("- `damage_by_indicative_zone.csv` — descriptive totals grouped by indicative zone.\n")
    lines.append("- `outputs/figures/w9_rq3_control_overlay.png` — the descriptive overlay map.\n")
    path = out_dir / "RQ3_FINDING.md"
    path.write_text("".join(lines), encoding="utf-8")
    return path


def plot_overlay(rows: Sequence[OverlayRow]) -> "Path | None":
    """A descriptive map: indicative control zones + per-AOI validated damage bubbles.

    Degrades gracefully (returns None) if geopandas/matplotlib/viz are unavailable —
    the CSV/markdown outputs never depend on a plotting backend.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import geopandas as gpd
        from viz import apply_theme, caveat_footer, save_figure
    except Exception:
        return None

    apply_theme()
    gov = gpd.read_file(REPO_ROOT / "aois" / "governorates.geojson")
    zones = gpd.read_file(CONTROL_AREAS)

    # indicative-admin fill colors (descriptive categories, NOT a ranking)
    admin_colors = {"former_AANES": "#7fb3d5", "government": "#f0b27a"}

    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(9, 8))
    # context: all governorates, light
    gov.boundary.plot(ax=ax, color="#cccccc", linewidth=0.6)
    # indicative zones, semi-transparent. geopandas polygon plots don't register as
    # legend handles, so build explicit proxy patches for the legend.
    legend_handles = []
    for admin, color in admin_colors.items():
        sub = zones[zones["indicative_admin"] == admin]
        if not sub.empty:
            sub.plot(ax=ax, color=color, alpha=0.45, edgecolor="#888888", linewidth=0.8)
            legend_handles.append(Patch(facecolor=color, alpha=0.45, edgecolor="#888888",
                                        label=f"{admin} (indicative)"))

    # per-AOI total validated damage bubbles at AOI centroids (in-scope AOIs only)
    total_by_aoi: dict[str, float] = defaultdict(float)
    for r in rows:
        if r.in_scope:
            total_by_aoi[r.aoi_id] += r.damaged_ha_headline_union
    gov_proj = gov.to_crs(3857)
    for _, g in gov_proj.iterrows():
        aoi = g["aoi_id"]
        if aoi not in total_by_aoi:
            continue
        c = g.geometry.centroid
        cpt = gpd.GeoSeries([c], crs=3857).to_crs(4326).iloc[0]
        ha = total_by_aoi[aoi]
        ax.scatter([cpt.x], [cpt.y], s=max(40, ha / 8.0), color="#c0392b",
                   alpha=0.7, edgecolor="black", zorder=5)
        ax.annotate(f"{aoi.replace('_', ' ')}\n{ha:,.0f} ha",
                    (cpt.x, cpt.y), fontsize=8, ha="center", va="center", zorder=6)

    ax.set_title("RQ3 — 2026 validated cropland damage vs INDICATIVE control zones\n"
                 "(descriptive overlay; no differential or causal claim — DEC-005)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    legend_handles.append(plt.Line2D([0], [0], marker="o", color="w",
                                     markerfacecolor="#c0392b", markeredgecolor="black",
                                     markersize=10, alpha=0.7,
                                     label="validated damage (ha; bubble area)"))
    ax.legend(handles=legend_handles, title="indicative zone (contested)",
              loc="lower left", fontsize=8)
    caveat_footer(
        fig,
        "INDICATIVE / CONTESTED boundaries — descriptive only (DEC-005); no differential "
        "or causal claim. Deir ez-Zor spans both zones (unapportioned). Bubble = total "
        "validated flood+fire damaged cropland (ha), first-half-2026 lower bound (DEC-039).",
    )
    return save_figure(fig, "w9_rq3_control_overlay")


# --- driver -------------------------------------------------------------------

def load_validated_records(flood_csv: Path = FLOOD_CSV, fire_csv: Path = FIRE_CSV) -> list[DamageRecord]:
    """Validated flood + fire records via the §6 hard gate (refuses non-validated)."""
    records: list[DamageRecord] = []
    if flood_csv.exists():
        records += gate_records(read_csv(flood_csv))
    if fire_csv.exists():
        records += gate_records(read_csv(fire_csv))
    return records


def main() -> None:
    records = load_validated_records()
    rows = build_overlay(records)
    p1, p2 = write_tables(rows)
    p3 = write_finding(rows)
    p4 = plot_overlay(rows)
    print(f"wrote {p1}")
    print(f"wrote {p2}")
    print(f"wrote {p3}")
    print(f"wrote {p4}" if p4 else "map skipped (geopandas/matplotlib/viz unavailable)")
    print("\nDescriptive damage by indicative zone (NO comparison implied):")
    for z in summarise_by_zone(rows):
        print(
            f"  {z['indicative_zone']:<55}  "
            f"flood={z['flood_ha_headline_union']:>9,.0f} ha  "
            f"fire={z['fire_ha_headline_union']:>9,.0f} ha"
        )


if __name__ == "__main__":
    main()
