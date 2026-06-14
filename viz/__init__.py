"""Shared visualization layer (docs/STRUCTURE.md §2 presentation layer; DEC-008).

The presentation layer is a static, reproducible Quarto report (not a dashboard).
Plotting functions live with the modules that own figure emission (food_security,
analysis, pipelines/*/attribution.py); this package gives them ONE consistent look
and enforces two project rules in code:

  * the validation gate — report figures consume only is_consumable() records
    (docs/STRUCTURE.md §6) via `consumable_records()`;
  * proportionate claims — caveats are stamped on figures via `caveat_footer()`
    (docs/PRODUCT.md §5, §9).
"""

from .maps import choropleth
from .style import (
    CAVEATS,
    PHENOMENON_COLORS,
    apply_theme,
    bar_value_labels,
    baseline_line,
    caveat_footer,
    consumable_records,
    records_to_dataframe,
    save_figure,
    validation_palette,
)

__all__ = [
    "CAVEATS",
    "PHENOMENON_COLORS",
    "apply_theme",
    "bar_value_labels",
    "baseline_line",
    "caveat_footer",
    "choropleth",
    "consumable_records",
    "records_to_dataframe",
    "save_figure",
    "validation_palette",
]
