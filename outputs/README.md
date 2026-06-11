# outputs/ — tables, masks, figures

Final analytical artifacts. Damage masks, the shared-schema damage tables, the
food-security impact tables, and RQ figures land here.

Reminder: any `damaged_cropland_ha` table or mask is a **Tier-2 human-gated**
output (`docs/STRUCTURE.md` §6). It is not "done" until a human has compared it
against named ground truth (floods → GloFAS + any Copernicus EMS flood
activation; fires → Copernicus EMS EMSR811, PAX as precedent). Carry
`validation_status` on every Tier-2 artifact; default `unvalidated`.
