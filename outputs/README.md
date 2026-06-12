# outputs/ — tables, masks, figures

Final analytical artifacts. Damage masks, the shared-schema damage tables, the
food-security impact tables, and RQ figures land here.

Reminder: any `damaged_cropland_ha` table or mask is a **Tier-2 human-gated**
output (`docs/STRUCTURE.md` §6). It is not "done" until a human has compared it
against named ground truth (floods → GloFAS + any Copernicus EMS flood
activation; fires → Copernicus EMS EMSR811, PAX as precedent). Carry
`validation_status` on every Tier-2 artifact; default `unvalidated`.

## Pipeline B (fires, W5/S7) artifacts — UNVALIDATED

- `tables/fire_damage.{csv,parquet}` — fire DamageRecords, **union headline**
  (DEC-032), all `validation_status=unvalidated`.
- `tables/fire_damage_sensitivity.csv` — union vs intersection range (DEC-015).
- `tables/fire_validation_anchor_emsr811.csv` — 2025 Latakia EMSR811 method
  anchor (baseline/context, DEC-001 — not a study record).
- `fire_hotspots/*_viirs.csv` — raw VIIRS detections (provenance).
- `fire_validation/` — **Tier-2 validation packet**: `VALIDATION_PACKET.md` +
  per-AOI `*_validation.png`. Start here for the human fire gate.
