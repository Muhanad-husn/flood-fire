# outputs/tables/ — shared-schema tables

Tabular artifacts in the canonical format (CSV/Parquet — format pinned in W0):

- shared-schema **damage tables** (`schema/damage_schema.py` records, both
  pipelines), each row carrying its `validation_status`;
- **food-security impact tables** (production loss, phase delta) from
  `food_security/impact_layer.py`.

Any `damaged_cropland_ha` table is a **Tier-2 human-gated** output
(`docs/STRUCTURE.md` §6): not "done" until validated against named ground truth.
Downstream figures/analyses consume validated rows only (`viz.consumable_records`).
