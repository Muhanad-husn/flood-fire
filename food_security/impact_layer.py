"""Food-security impact layer — the §3.4 join contract (docs/STRUCTURE.md §7 W6).

Chain: damaged_cropland_ha -> estimated production loss -> food-security phase
delta, joined to GIEWS / FEWS NET / IPC (and WFP / FAO ASIS as available),
referenced against the 2025 drought baseline (§3.3).

CONSUMES ONLY validated records (§6): must refuse any DamageRecord whose
validation_status != "validated". Reads the shared damage schema (§3.2) only —
never a pipeline's internal rasters.
"""

# TODO(W6): filter to validated records (DamageRecord.is_consumable); convert
# hectares -> production loss -> phase delta against baseline/.
