"""Pipeline B — burn scar + severity -> damaged_cropland_ha (docs/STRUCTURE.md §4).

Sentinel-2 dNBR for scar and severity; intersect with the canonical cropland
mask (aois/, §3.1) to get burned-cropland hectares. Emits
DamageRecord(phenomenon=FIRE) into the shared schema (§3.2).

Tier-2 human-gated (§6): validate against Copernicus EMS EMSR811; PAX
Sentinel-2 methodology as precedent. validation_status defaults to
"unvalidated".

GEE IDs (verify, §5): COPERNICUS/S2_SR_HARMONIZED
"""

# TODO(W5): compute dNBR; bin severity; intersect cropland mask; emit records.
