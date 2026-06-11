"""Pipeline A — intersect flood masks with the cropland mask -> damaged_cropland_ha.

Consumes the canonical cropland mask from aois/ (§3.1) and flood masks from
flood_mask.py. Emits DamageRecord(phenomenon=FLOOD) per AOI/date into the
shared schema (§3.2). validation_status defaults to "unvalidated" (Tier-2, §6).
"""

# TODO(W4): intersect flood extent x cropland mask; compute hectares; emit records.
