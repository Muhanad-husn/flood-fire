"""Shared figure styling + the two enforced project rules (DEC-008).

This module is the single place the report's look is defined and the place where
the validation gate and caveat discipline are enforced in code rather than left to
each plot author to remember.

Usage in a plot function (e.g. analysis/whiplash.py, food_security/impact_layer.py)::

    import matplotlib.pyplot as plt
    from viz import apply_theme, consumable_records, records_to_dataframe, \
        caveat_footer, save_figure

    apply_theme()
    df = records_to_dataframe(consumable_records(records))   # validated only
    fig, ax = plt.subplots()
    ...                                                       # seaborn/matplotlib
    caveat_footer(fig, CAVEATS["attribution"])
    save_figure(fig, "rq1_rainfall_vs_discharge")

`consumable_records()` is the hard gate (docs/STRUCTURE.md §6): every report figure
that makes a food-security or RQ claim must pass its records through it first.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from schema import DamageRecord, Phenomenon, ValidationStatus

# --- where rendered figures land (docs/STRUCTURE.md §2) -----------------------
# outputs/**/*.png is gitignored — figures are regenerated from code, never the
# source of truth. The report embeds them at render time.
FIGURES_DIR = Path(__file__).resolve().parent.parent / "outputs" / "figures"

# --- palette ------------------------------------------------------------------
# The analytical spine is the drought (baseline) -> water (flood, anomaly) +
# fire contrast, so the two phenomena read as clearly distinct.
PHENOMENON_COLORS: dict[Phenomenon, str] = {
    Phenomenon.FLOOD: "#1f77b4",  # water — blue
    Phenomenon.FIRE: "#d62728",   # fire — red
}

# Visual encoding for validation status. Report figures show only VALIDATED data;
# the exploration/validation notebooks (notebooks/) may show the others, clearly
# differentiated, while a human works the Tier-2 gate.
_VALIDATION_PALETTE: dict[ValidationStatus, str] = {
    ValidationStatus.VALIDATED: "#2ca02c",    # green — consumable
    ValidationStatus.UNVALIDATED: "#bbbbbb",  # grey — not yet human-checked
    ValidationStatus.REJECTED: "#e377c2",     # pink — failed the gate
}

# --- standard caveats (docs/PRODUCT.md §5, §9) --------------------------------
# Proportionate-claims discipline, stamped on the figures it applies to.
CAVEATS: dict[str, str] = {
    "control_areas": (
        "Control-area boundaries are contested and indicative only. Descriptive "
        "overlay (RQ3) — no differential or causal claim is made."
    ),
    "attribution": (
        "Attribution is provisional; rainfall-vs-discharge decomposition carries "
        "explicit uncertainty. See accompanying confidence bounds and caveats."
    ),
    "validated_only": (
        "Shows human-validated (Tier-2) records only; unvalidated detections are "
        "excluded (docs/STRUCTURE.md §6)."
    ),
    "case_study_2026h1": (
        "First-half-2026 case study (floods Mar–Jun; fires May 1 – Jun 12). The "
        "summer harvest/fire peak is unobserved, so headline figures are LOWER "
        "BOUNDS — re-run post-harvest for the full-year result (DEC-039)."
    ),
}


def apply_theme() -> None:
    """Set the project-wide seaborn/matplotlib theme. Call once per figure module.

    Centralizing the look here means the whole report is themed from one place.
    Imported lazily so the gate/filter helpers stay usable without a plotting
    backend installed (e.g. in lightweight tests).
    """
    import seaborn as sns

    sns.set_theme(
        context="notebook",
        style="whitegrid",
        palette="deep",
        font_scale=1.0,
    )


def validation_palette() -> dict[str, str]:
    """Return the validation-status color map keyed by status value (str).

    Keyed by the enum *value* so it drops straight into seaborn's ``palette=``
    when a ``validation_status`` column holds plain strings.
    """
    return {status.value: color for status, color in _VALIDATION_PALETTE.items()}


def consumable_records(records: Iterable[DamageRecord]) -> list[DamageRecord]:
    """The hard validation gate (docs/STRUCTURE.md §6).

    Filter to records a downstream figure/analysis may consume — i.e. only those
    a human has validated. Every report figure making a food-security or RQ claim
    must pass its records through this first. Mirrors DamageRecord.is_consumable().
    """
    return [r for r in records if r.is_consumable()]


def records_to_dataframe(records: Iterable[DamageRecord]):
    """Flatten DamageRecords into a tidy DataFrame for seaborn/matplotlib.

    Enum fields are emitted as their string values so they slot directly into
    seaborn ``hue=``/``x=`` and the palettes above. Does NOT filter — call
    `consumable_records()` first for any claim-bearing figure.
    """
    import pandas as pd

    return pd.DataFrame(
        {
            "aoi_id": r.aoi_id,
            "date": r.date,
            "phenomenon": r.phenomenon.value,
            "severity_class": r.severity_class,
            "source_layer": r.source_layer,
            "damaged_cropland_ha": r.damaged_cropland_ha,
            "validation_status": r.validation_status.value,
        }
        for r in records
    )


def caveat_footer(fig, text: str) -> None:
    """Stamp a caveat across the bottom of a figure (proportionate claims, §9).

    Use the standard strings in CAVEATS where one applies (control areas,
    attribution) so the same wording rides every figure it should.
    """
    fig.subplots_adjust(bottom=0.18)
    fig.text(
        0.5,
        0.02,
        text,
        ha="center",
        va="bottom",
        fontsize=8,
        style="italic",
        color="#555555",
        wrap=True,
    )


def bar_value_labels(ax, *, fmt: str = "{:,.0f}", fontsize: int = 7,
                     min_height: float = 0.0, threshold: float | None = None) -> None:
    """Print each bar's value above it so readers don't eyeball against the axis.

    Skips bars at/below ``min_height`` (e.g. zero-height hue gaps from seaborn's
    grouped bars). ``threshold`` is an alias kept for readable call sites.
    """
    cutoff = threshold if threshold is not None else min_height
    for container in ax.containers:
        labels = [fmt.format(v) if v > cutoff else "" for v in container.datavalues]
        ax.bar_label(container, labels=labels, padding=2, fontsize=fontsize,
                     color="#333333")


def baseline_line(ax, y: float, label: str, *, color: str = "#444444") -> None:
    """Draw a horizontal reference line (e.g. the 2025 drought baseline/plateau).

    Anchors the 'shock' to the analytical spine visually, not only in prose.
    """
    ax.axhline(y, color=color, linestyle="--", linewidth=1.0, zorder=0)
    ax.text(0.995, y, f" {label}", transform=ax.get_yaxis_transform(),
            ha="right", va="bottom", fontsize=7.5, style="italic", color=color)


def save_figure(fig, name: str, *, dpi: int = 150) -> Path:
    """Save a figure to outputs/figures/<name>.png and return its path.

    Created on demand; the directory is gitignored for PNGs (regenerated from
    code). Returns the path so callers/notebooks can embed or log it.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURES_DIR / f"{name}.png"
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    return out
