"""Food-security impact layer — the §3.4 join contract (docs/STRUCTURE.md §7 W6).

Chain: damaged_cropland_ha -> estimated production loss -> food-security phase
delta, referenced against the 2025 drought baseline (§3.3) and framed against
GIEWS / FEWS NET / IPC.

CONSUMES ONLY validated records (§6): refuses any DamageRecord whose
validation_status != "validated" (the `gate_records` hard gate). Reads the shared
damage schema (§3.2) only — never a pipeline's internal rasters.

Method (the load-bearing analytical choices — see DEC-033):

  * Cropland-definition sensitivity (DEC-015): the UNION cropland is the headline,
    the INTERSECTION is the conservative low bound. Per the S8 standardisation, the
    flood pipeline's two-row union/intersection encoding (DEC-024) and the fire
    pipeline's union-headline + sensitivity-side-table encoding (DEC-032) are both
    normalised onto one union-headline + intersection-low convention here, so the
    food-security layer reads one consistent headline across phenomena and never
    double-counts the flood rows.

  * Temporal aggregation (floods only). Flood records are PER EVENT-DATE; a
    `persistent` cropland pixel (flooded on >=2 dates, DEC-024) appears on every
    date it floods, so summing hectares across dates would double-count it.
    Headline flood-affected cropland per AOI = the PEAK single event-date extent
    (transient + persistent on the worst date) — a clean, assumption-light snapshot
    and a conservative lower bound on the season footprint (matches the S6 handoff
    headlines). A larger season-distinct reference (sum of transient across dates +
    peak persistent, which avoids the persistent double-count) is also reported as
    an upper bracket. Fires carry a single window with disjoint severity classes, so
    summing severity is exact — no temporal double-count.

  * Production loss = damaged_cropland_ha * the per-AOI 2025 baseline cereal yield
    (cereal_production_2025_t / cropland_ha from baseline/production_baseline.csv,
    DEC-019). That yield is the DROUGHT-FLOOR yield (the ~1.2 Mt 2025 collapse), so
    applying it to 2026 damaged area is a deliberately CONSERVATIVE loss estimate:
    2026 was a tentative recovery (PRODUCT §2), so true expected yields on the lost
    hectares were almost certainly higher. Loss is therefore a lower bound.

  * Food-security "phase delta" (§3.4). We do NOT assign IPC phase numbers — a real
    IPC classification needs the full protocol (consumption, livelihoods, nutrition,
    mortality), not cropland loss alone. Instead we report production loss as a
    percent of the already-deficit 2025 baseline and an explicitly INDICATIVE,
    non-IPC food-security pressure label, attributed to GIEWS / FEWS NET / IPC as the
    authoritative sources for the actual phase. Proportionate claims (§9): this is a
    production-shock SIGNAL that feeds, not replaces, an IPC assessment.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from schema.damage_schema import DamageRecord, Phenomenon, read_csv

# --- paths (docs/STRUCTURE.md §2) ---------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
FLOOD_CSV = REPO_ROOT / "outputs" / "floods" / "flood_damage.csv"
FIRE_CSV = REPO_ROOT / "outputs" / "tables" / "fire_damage.csv"
FIRE_SENSITIVITY_CSV = REPO_ROOT / "outputs" / "tables" / "fire_damage_sensitivity.csv"
BASELINE_CSV = REPO_ROOT / "baseline" / "production_baseline.csv"
OUT_DIR = REPO_ROOT / "outputs" / "food_security"

STUDY_AOIS: tuple[str, ...] = ("deir_ez_zor", "raqqa", "hasakah", "latakia")
NATIONAL_CEREAL_FLOOR_2025_T = 1_200_000  # FAO/GIEWS ~1.2 Mt floor (DEC-019)


# --- the §6 validation gate (hard rule) ---------------------------------------

class ValidationGateError(RuntimeError):
    """A non-validated DamageRecord reached the food-security layer (§6)."""


def gate_records(records: Iterable[DamageRecord], *, strict: bool = True) -> list[DamageRecord]:
    """Apply the §6 hard gate: keep only `is_consumable()` (human-validated) records.

    The food-security layer must REFUSE to consume any record whose
    validation_status != "validated" (docs/STRUCTURE.md §6). In ``strict`` mode
    (the default) a non-validated record raises rather than being silently dropped,
    so a half-validated pipeline cannot be quietly consumed. Tier-2 status is set
    only by a human (§6, DEC-007); nothing here can confer it.
    """
    consumable: list[DamageRecord] = []
    rejected: list[DamageRecord] = []
    for r in records:
        (consumable if r.is_consumable() else rejected).append(r)
    if strict and rejected:
        sample = rejected[0]
        raise ValidationGateError(
            f"{len(rejected)} non-validated record(s) reached the food-security "
            f"gate; refusing to consume (docs/STRUCTURE.md §6). First offender: "
            f"{sample.aoi_id} {sample.date} {sample.phenomenon.value} "
            f"status={sample.validation_status.value}"
        )
    return consumable


# --- damaged-hectare aggregation per AOI --------------------------------------

@dataclass
class AoiDamage:
    """Aggregated flood OR fire damaged cropland for one AOI (hectares)."""

    aoi_id: str
    phenomenon: str           # "flood" | "fire"
    ha_headline: float        # UNION cropland, conservative temporal aggregation
    ha_low: float             # INTERSECTION cropland (cropland-definition low bound)
    ha_season_ref: float      # season-distinct UNION upper reference (== headline for fires)


def _flood_cdef(records: Sequence[DamageRecord], suffix: str) -> list[DamageRecord]:
    """Flood records for one cropland definition, identified by source_layer suffix.

    DEC-024 encodes union vs intersection in source_layer
    (`S1_GRD_changedet+cropland_union` / `…+cropland_intersection`).
    """
    return [r for r in records if r.source_layer.endswith(suffix)]


def _peak_and_season(records: Sequence[DamageRecord]) -> tuple[float, float]:
    """(peak single-date extent, season-distinct estimate) for one cropland def.

    peak  = max over event dates of (transient + persistent) on that date — a clean
            snapshot, no cross-date double-count.
    season = sum(transient over all dates) + max(persistent over dates). Transient
            pixels are flooded exactly once (globally disjoint across dates), so
            summing them is exact; persistent pixels recur, so only their peak-date
            extent is added (avoids the persistent double-count). A lower bound on
            the true season footprint, and an upper bracket relative to `peak`.
    """
    per_date: dict[str, dict[str, float]] = defaultdict(lambda: {"transient": 0.0, "persistent": 0.0})
    for r in records:
        if r.severity_class in ("transient", "persistent"):
            per_date[r.date][r.severity_class] += r.damaged_cropland_ha
        # permanent_excluded is a 0-ha exclusion class — ignored.
    if not per_date:
        return 0.0, 0.0
    peak = max(v["transient"] + v["persistent"] for v in per_date.values())
    transient_sum = sum(v["transient"] for v in per_date.values())
    persistent_peak = max(v["persistent"] for v in per_date.values())
    return peak, transient_sum + persistent_peak


def aggregate_floods(records: Iterable[DamageRecord]) -> dict[str, AoiDamage]:
    """Per-AOI flood damaged-cropland aggregation (validated flood records in)."""
    floods = [r for r in records if r.phenomenon is Phenomenon.FLOOD]
    by_aoi: dict[str, list[DamageRecord]] = defaultdict(list)
    for r in floods:
        by_aoi[r.aoi_id].append(r)

    out: dict[str, AoiDamage] = {}
    for aoi, recs in by_aoi.items():
        peak_u, season_u = _peak_and_season(_flood_cdef(recs, "cropland_union"))
        peak_i, _ = _peak_and_season(_flood_cdef(recs, "cropland_intersection"))
        out[aoi] = AoiDamage(
            aoi_id=aoi,
            phenomenon="flood",
            ha_headline=round(peak_u, 2),
            ha_low=round(peak_i, 2),
            ha_season_ref=round(season_u, 2),
        )
    return out


def _fire_intersection_ha(path: Path) -> dict[str, float]:
    """Per-AOI 2026-study intersection burned ha from the fire sensitivity table.

    The fire DamageRecords carry the UNION headline (DEC-032); the intersection low
    bound lives in fire_damage_sensitivity.csv. Only 2026 study rows are summed —
    the 2025 EMSR811 anchor is method-validation context, never a study record
    (DEC-001).
    """
    if not path.exists():
        return {}
    totals: dict[str, float] = defaultdict(float)
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("window")) == "2026" and str(row.get("is_study")).lower() == "true":
                totals[row["aoi_id"]] += float(row["ha_intersection"])
    return dict(totals)


def aggregate_fires(records: Iterable[DamageRecord], sensitivity_csv: Path = FIRE_SENSITIVITY_CSV) -> dict[str, AoiDamage]:
    """Per-AOI fire damaged-cropland aggregation (validated fire records in).

    One window, disjoint severity classes -> summing severity is exact. Union
    headline from the records (DEC-032); intersection low from the sensitivity table.
    """
    fires = [r for r in records if r.phenomenon is Phenomenon.FIRE]
    union_by_aoi: dict[str, float] = defaultdict(float)
    for r in fires:
        if r.severity_class != "unburned":  # non-damage class, 0 ha anyway
            union_by_aoi[r.aoi_id] += r.damaged_cropland_ha

    inter_by_aoi = _fire_intersection_ha(sensitivity_csv)
    out: dict[str, AoiDamage] = {}
    for aoi, ha_u in union_by_aoi.items():
        out[aoi] = AoiDamage(
            aoi_id=aoi,
            phenomenon="fire",
            ha_headline=round(ha_u, 2),
            ha_low=round(inter_by_aoi.get(aoi, ha_u), 2),
            ha_season_ref=round(ha_u, 2),  # no temporal double-count for fires
        )
    return out


# --- baseline yield + production loss -----------------------------------------

@dataclass
class Baseline:
    aoi_id: str
    cropland_ha: float
    production_2025_t: float

    @property
    def yield_t_ha(self) -> float:
        return self.production_2025_t / self.cropland_ha if self.cropland_ha else 0.0


def load_baseline(path: Path = BASELINE_CSV) -> dict[str, Baseline]:
    """Per-study-AOI 2025 baseline (production floor + cropland) from §3.3 (DEC-019)."""
    out: dict[str, Baseline] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            aoi = row["aoi_id"].strip()
            if not aoi or str(row["is_study_aoi"]).lower() != "true":
                continue
            out[aoi] = Baseline(
                aoi_id=aoi,
                cropland_ha=float(row["cropland_ha"]),
                production_2025_t=float(row["cereal_production_2025_t"]),
            )
    return out


# --- indicative food-security pressure (non-IPC, §3.4 / §9) --------------------

def pressure_label(loss_pct_of_baseline: float) -> str:
    """An INDICATIVE, non-IPC food-security pressure tag from production-loss %.

    NOT an IPC phase. Maps the incremental cereal-production loss (as a percent of
    the already-deficit 2025 drought baseline) to a qualitative pressure band. The
    authoritative phase classification is GIEWS / FEWS NET / IPC; this is a
    production-shock signal feeding such an assessment (proportionate claims, §9).
    """
    p = loss_pct_of_baseline
    if p < 1.0:
        return "marginal"
    if p < 5.0:
        return "moderate incremental stress"
    if p < 15.0:
        return "significant incremental stress"
    return "severe incremental stress"


@dataclass
class AoiImpact:
    aoi_id: str
    phenomenon: str
    damaged_ha_headline_union: float
    damaged_ha_low_intersection: float
    damaged_ha_season_ref_union: float
    baseline_yield_t_ha: float
    baseline_production_2025_t: float
    production_loss_t_headline: float
    production_loss_t_low: float
    production_loss_t_season_ref: float
    loss_pct_of_baseline_headline: float


def compute_impact(
    flood_csv: Path = FLOOD_CSV,
    fire_csv: Path = FIRE_CSV,
    baseline_csv: Path = BASELINE_CSV,
    sensitivity_csv: Path = FIRE_SENSITIVITY_CSV,
) -> list[AoiImpact]:
    """The §3.4 chain: validated records -> per-AOI/-phenomenon production-loss rows."""
    records: list[DamageRecord] = []
    if flood_csv.exists():
        records += gate_records(read_csv(flood_csv))
    if fire_csv.exists():
        records += gate_records(read_csv(fire_csv))

    flood_dmg = aggregate_floods(records)
    fire_dmg = aggregate_fires(records, sensitivity_csv)
    baseline = load_baseline(baseline_csv)

    rows: list[AoiImpact] = []
    for dmg_map in (flood_dmg, fire_dmg):
        for aoi, d in sorted(dmg_map.items()):
            b = baseline.get(aoi)
            if b is None:
                continue
            y = b.yield_t_ha
            loss_head = d.ha_headline * y
            rows.append(
                AoiImpact(
                    aoi_id=aoi,
                    phenomenon=d.phenomenon,
                    damaged_ha_headline_union=d.ha_headline,
                    damaged_ha_low_intersection=d.ha_low,
                    damaged_ha_season_ref_union=d.ha_season_ref,
                    baseline_yield_t_ha=round(y, 4),
                    baseline_production_2025_t=round(b.production_2025_t, 1),
                    production_loss_t_headline=round(loss_head, 1),
                    production_loss_t_low=round(d.ha_low * y, 1),
                    production_loss_t_season_ref=round(d.ha_season_ref * y, 1),
                    loss_pct_of_baseline_headline=round(
                        100 * loss_head / b.production_2025_t, 3
                    ) if b.production_2025_t else 0.0,
                )
            )
    return rows


# --- output tables + figures --------------------------------------------------

_BY_AOI_FIELDS = (
    "aoi_id", "phenomenon",
    "damaged_ha_headline_union", "damaged_ha_low_intersection", "damaged_ha_season_ref_union",
    "baseline_yield_t_ha", "baseline_production_2025_t",
    "production_loss_t_headline", "production_loss_t_low", "production_loss_t_season_ref",
    "loss_pct_of_baseline_headline",
)


def write_by_aoi(rows: Sequence[AoiImpact], out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "impact_by_aoi.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_BY_AOI_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: getattr(r, k) for k in _BY_AOI_FIELDS})
    return path


def summarise_national(rows: Sequence[AoiImpact]) -> list[dict[str, object]]:
    """Per-AOI combined (flood+fire) + a study-area total, vs the 2025 floor."""
    by_aoi: dict[str, dict[str, float]] = defaultdict(lambda: {
        "loss_head": 0.0, "loss_low": 0.0, "loss_season": 0.0, "baseline": 0.0,
    })
    baselines: dict[str, float] = {}
    for r in rows:
        a = by_aoi[r.aoi_id]
        a["loss_head"] += r.production_loss_t_headline
        a["loss_low"] += r.production_loss_t_low
        a["loss_season"] += r.production_loss_t_season_ref
        baselines[r.aoi_id] = r.baseline_production_2025_t
    out: list[dict[str, object]] = []
    tot = {"loss_head": 0.0, "loss_low": 0.0, "loss_season": 0.0, "baseline": 0.0}
    for aoi in sorted(by_aoi):
        base = baselines[aoi]
        a = by_aoi[aoi]
        out.append({
            "aoi_id": aoi,
            "baseline_production_2025_t": round(base, 1),
            "production_loss_t_headline": round(a["loss_head"], 1),
            "production_loss_t_low": round(a["loss_low"], 1),
            "production_loss_t_season_ref": round(a["loss_season"], 1),
            "loss_pct_of_baseline_headline": round(100 * a["loss_head"] / base, 3) if base else 0.0,
            "food_security_pressure_indicative": pressure_label(100 * a["loss_head"] / base if base else 0.0),
        })
        tot["loss_head"] += a["loss_head"]
        tot["loss_low"] += a["loss_low"]
        tot["loss_season"] += a["loss_season"]
        tot["baseline"] += base
    out.append({
        "aoi_id": "STUDY_TOTAL",
        "baseline_production_2025_t": round(tot["baseline"], 1),
        "production_loss_t_headline": round(tot["loss_head"], 1),
        "production_loss_t_low": round(tot["loss_low"], 1),
        "production_loss_t_season_ref": round(tot["loss_season"], 1),
        "loss_pct_of_baseline_headline": round(100 * tot["loss_head"] / tot["baseline"], 3) if tot["baseline"] else 0.0,
        "food_security_pressure_indicative": pressure_label(100 * tot["loss_head"] / tot["baseline"] if tot["baseline"] else 0.0),
    })
    return out


_NATIONAL_FIELDS = (
    "aoi_id", "baseline_production_2025_t",
    "production_loss_t_headline", "production_loss_t_low", "production_loss_t_season_ref",
    "loss_pct_of_baseline_headline", "food_security_pressure_indicative",
)


def write_national(rows: Sequence[AoiImpact], out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "impact_national.csv"
    summary = summarise_national(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_NATIONAL_FIELDS)
        w.writeheader()
        for row in summary:
            w.writerow(row)
    return path


def plot_production_loss(rows: Sequence[AoiImpact], out_dir: Path = OUT_DIR) -> Path | None:
    """Grouped bar of headline production loss (t) by AOI and phenomenon.

    Validated-only by construction (rows derive from gate_records). Stamps the
    validated-only caveat (proportionate claims, §9 / DEC-008).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from viz import apply_theme, caveat_footer, save_figure, CAVEATS
    except Exception:
        return None

    apply_theme()
    aois = sorted({r.aoi_id for r in rows})
    phenom = ["flood", "fire"]
    colors = {"flood": "#1f77b4", "fire": "#d62728"}
    loss = {(r.aoi_id, r.phenomenon): r.production_loss_t_headline for r in rows}

    import numpy as np
    x = np.arange(len(aois))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, ph in enumerate(phenom):
        vals = [loss.get((a, ph), 0.0) for a in aois]
        ax.bar(x + (i - 0.5) * w, vals, w, label=ph, color=colors[ph])
    ax.set_xticks(x)
    ax.set_xticklabels([a.replace("_", " ") for a in aois])
    ax.set_ylabel("Estimated cereal-production loss (t, headline)")
    ax.set_title("2026 flood & fire production loss vs 2025 drought baseline")
    ax.legend(title="phenomenon")
    caveat_footer(
        fig,
        CAVEATS["validated_only"] + " Loss at conservative 2025 drought-floor yields "
        "— a lower bound (see IMPACT_README).",
    )
    return save_figure(fig, "w6_food_security_production_loss")


# --- README / method + caveats note -------------------------------------------

def write_readme(rows: Sequence[AoiImpact], out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    nat = summarise_national(rows)
    total = next(r for r in nat if r["aoi_id"] == "STUDY_TOTAL")
    lines: list[str] = []
    lines.append("# W6 — Food-security impact layer (docs/STRUCTURE.md §3.4)\n")
    lines.append(
        "Translates **human-validated** flood & fire `damaged_cropland_ha` records "
        "(§3.2, §6) into estimated cereal-production loss and an indicative "
        "food-security pressure, referenced to the 2025 drought baseline (§3.3).\n"
    )
    lines.append("## Headline (study AOIs, combined flood + fire)\n")
    lines.append(
        f"- **Estimated cereal-production loss:** ~**{total['production_loss_t_headline']:,.0f} t** "
        f"(headline) — range **{total['production_loss_t_low']:,.0f}–"
        f"{total['production_loss_t_season_ref']:,.0f} t** "
        "(cropland-definition × temporal-aggregation sensitivity).\n"
    )
    lines.append(
        f"- That is **{total['loss_pct_of_baseline_headline']:.2f}%** of the four study AOIs' "
        f"combined 2025 baseline ({total['baseline_production_2025_t']:,.0f} t), and "
        f"{100 * total['production_loss_t_headline'] / NATIONAL_CEREAL_FLOOR_2025_T:.2f}% of the "
        f"national ~1.2 Mt 2025 cereal floor.\n"
    )
    lines.append(
        f"- Indicative food-security pressure (study total): "
        f"**{total['food_security_pressure_indicative']}** — *not* an IPC phase (see caveats).\n"
    )
    lines.append("\n## Method (DEC-033)\n")
    lines.append(
        "1. **Validated-only gate (§6).** Only `is_consumable()` records are read; a "
        "non-validated record makes the layer refuse (`gate_records`, strict). No "
        "agent set any `validation_status` — the floods (S6) and fires (S7) Tier-2 "
        "gates were closed by a human.\n"
    )
    lines.append(
        "2. **One cropland convention.** UNION cropland (DEC-015) is the headline, "
        "INTERSECTION the conservative low bound. The flood two-row encoding "
        "(DEC-024) and the fire union-headline + sensitivity-table encoding "
        "(DEC-032) are normalised onto union-headline here — so flood rows are **not** "
        "double-counted across cropland definitions.\n"
    )
    lines.append(
        "3. **No temporal double-count (floods).** Flood records are per event-date; a "
        "`persistent` pixel recurs across dates. Headline flood-affected cropland per "
        "AOI = the **peak single event-date** extent (transient+persistent) — a clean "
        "snapshot, conservative lower bound. A season-distinct reference "
        "(Σ transient + peak persistent) is the upper bracket. Fires = one window, "
        "disjoint severity → exact.\n"
    )
    lines.append(
        "4. **Loss = ha × 2025 baseline yield** (per-AOI `cereal_production_2025_t / "
        "cropland_ha`, DEC-019 — a uniform ~0.223 t/ha drought-floor yield). Applying "
        "the drought-year yield to 2026 damaged area makes the loss a **conservative "
        "lower bound**: 2026 was a tentative recovery (PRODUCT §2), so expected yields "
        "on the lost hectares were higher.\n"
    )
    lines.append("\n## Confidence & caveats (proportionate claims, §9)\n")
    lines.append(
        "- **Not an IPC classification.** The `food_security_pressure_indicative` "
        "label is a qualitative band from production-loss-as-%-of-baseline, **not** an "
        "IPC phase. A real phase needs the full IPC protocol (consumption, "
        "livelihoods, nutrition, mortality). **GIEWS / FEWS NET / IPC** are the "
        "authoritative sources; this layer is a production-shock signal that feeds, "
        "not replaces, such an assessment. Syria's 2025 baseline was already a "
        "record-drought Crisis-level food-security context (PRODUCT §2) — the 2026 "
        "shock is **incremental** pressure on top of that.\n"
    )
    lines.append(
        "- **Loss is a lower bound** on two counts: conservative drought-floor yield, "
        "and the peak-date (not season-union) flood aggregation. The reported range "
        "brackets the cropland-definition and temporal-aggregation uncertainty; it "
        "does **not** add yield-recovery uncertainty.\n"
    )
    lines.append(
        "- **Damage hectares inherit the pipeline caveats:** flood extent is "
        "open-water riverine inundation (flooded vegetation / pluvial upland "
        "under-detected, DEC-023); burned cropland is VIIRS-confirmed dNBR, a "
        "conservative lower bound (DEC-031). Latakia 2026 fire ≈ 1 ha because the "
        "July fire peak is in the simulated future (S7) — a data-availability gap, "
        "not absence of risk.\n"
    )
    lines.append("\n## Outputs\n")
    lines.append("- `impact_by_aoi.csv` — per AOI × phenomenon: damaged ha (headline/low/season), yield, loss (t), loss % of baseline.\n")
    lines.append("- `impact_national.csv` — per-AOI combined + study total vs the 2025 floor + indicative pressure.\n")
    lines.append("- `outputs/figures/w6_food_security_production_loss.png` — headline loss by AOI & phenomenon.\n")
    path = out_dir / "IMPACT_README.md"
    path.write_text("".join(lines), encoding="utf-8")
    return path


def main() -> None:
    rows = compute_impact()
    p1 = write_by_aoi(rows)
    p2 = write_national(rows)
    p3 = write_readme(rows)
    p4 = plot_production_loss(rows)
    print(f"wrote {p1}")
    print(f"wrote {p2}")
    print(f"wrote {p3}")
    print(f"wrote {p4}" if p4 else "figure skipped (matplotlib/viz unavailable)")
    for r in summarise_national(rows):
        print(
            f"  {r['aoi_id']:>12}  loss={r['production_loss_t_headline']:>10,.0f} t  "
            f"({r['loss_pct_of_baseline_headline']:>6.2f}% of baseline)  "
            f"{r['food_security_pressure_indicative']}"
        )


if __name__ == "__main__":
    main()
