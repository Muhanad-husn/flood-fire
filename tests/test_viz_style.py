"""The validation gate must hold in the presentation layer (docs/STRUCTURE.md §6).

Report figures consume only human-validated records. `consumable_records()` is the
code-level enforcement; this asserts it lets exactly the VALIDATED records through
and drops UNVALIDATED + REJECTED. Pure-data test — no plotting backend required.
"""

from schema import DamageRecord, Phenomenon, ValidationStatus
from viz import consumable_records


def _record(aoi_id: str, status: ValidationStatus) -> DamageRecord:
    return DamageRecord(
        aoi_id=aoi_id,
        date="2026-05-30",
        phenomenon=Phenomenon.FLOOD,
        severity_class="high",
        source_layer="S1_GRD",
        damaged_cropland_ha=123.4,
        validation_status=status,
    )


def test_consumable_records_keeps_only_validated():
    records = [
        _record("deir_ez_zor", ValidationStatus.VALIDATED),
        _record("raqqa", ValidationStatus.UNVALIDATED),
        _record("hasakah", ValidationStatus.REJECTED),
        _record("raqqa", ValidationStatus.VALIDATED),
    ]

    kept = consumable_records(records)

    assert len(kept) == 2
    assert all(r.validation_status is ValidationStatus.VALIDATED for r in kept)
    assert {r.aoi_id for r in kept} == {"deir_ez_zor", "raqqa"}


def test_consumable_records_default_status_is_excluded():
    # DamageRecord defaults to UNVALIDATED — a freshly emitted Tier-2 record must
    # never reach a report figure until a human validates it.
    fresh = DamageRecord(
        aoi_id="hasakah",
        date="2026-06-12",
        phenomenon=Phenomenon.FIRE,
        severity_class="moderate",
        source_layer="S2_dNBR",
        damaged_cropland_ha=42.0,
    )

    assert fresh.validation_status is ValidationStatus.UNVALIDATED
    assert consumable_records([fresh]) == []


def test_consumable_records_empty_input():
    assert consumable_records([]) == []
