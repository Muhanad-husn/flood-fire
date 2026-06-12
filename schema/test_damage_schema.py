"""Tier-1 tests for the shared damage schema (docs/STRUCTURE.md §3.2, §6).

Covers: severity vocab per phenomenon, the consumable gate, and lossless CSV +
Parquet round-trips. Parquet tests skip cleanly if pandas/pyarrow are absent so
the core schema stays runnable without the geo env. Run: `pytest schema/`.
"""

from __future__ import annotations

import pytest

from schema.damage_schema import (
    DamageRecord,
    Phenomenon,
    SchemaError,
    ValidationStatus,
    from_row,
    read_csv,
    read_parquet,
    to_row,
    validate_record,
    write_csv,
    write_parquet,
)


def _sample() -> list[DamageRecord]:
    return [
        DamageRecord("deir_ez_zor", "2026-05-28", Phenomenon.FLOOD, "persistent", "S1_GRD", 1234.5),
        DamageRecord("hasakah", "2026-06-10", Phenomenon.FIRE, "high", "S2_dNBR", 88.0,
                     ValidationStatus.VALIDATED),
        DamageRecord("raqqa", "2026-04-15", Phenomenon.FLOOD, "permanent_excluded", "JRC_GSW", 0.0),
    ]


def test_is_consumable_only_for_validated():
    recs = _sample()
    assert recs[0].is_consumable() is False           # unvalidated default
    assert recs[1].is_consumable() is True             # human-validated
    assert DamageRecord("x", "2026-01-01", Phenomenon.FIRE, "high", "S2", 1.0,
                        ValidationStatus.REJECTED).is_consumable() is False


def test_severity_class_is_per_phenomenon():
    # a fire bin is invalid for a flood record and vice versa
    with pytest.raises(SchemaError):
        validate_record(DamageRecord("x", "2026-01-01", Phenomenon.FLOOD, "high", "S1", 1.0))
    with pytest.raises(SchemaError):
        validate_record(DamageRecord("x", "2026-01-01", Phenomenon.FIRE, "persistent", "S2", 1.0))


def test_non_damage_class_must_be_zero_ha():
    with pytest.raises(SchemaError):
        validate_record(DamageRecord("x", "2026-01-01", Phenomenon.FLOOD, "permanent_excluded", "JRC", 5.0))
    with pytest.raises(SchemaError):
        validate_record(DamageRecord("x", "2026-01-01", Phenomenon.FIRE, "unburned", "S2_dNBR", 5.0))


def test_negative_ha_rejected():
    with pytest.raises(SchemaError):
        validate_record(DamageRecord("x", "2026-01-01", Phenomenon.FIRE, "high", "S2", -1.0))


def test_row_coerces_strings_back_to_enums():
    rec = _sample()[1]
    row = to_row(rec)
    assert row["phenomenon"] == "fire" and row["validation_status"] == "validated"
    assert from_row(row) == rec
    assert isinstance(from_row(row).phenomenon, Phenomenon)


def test_csv_round_trip_lossless(tmp_path):
    recs = _sample()
    p = write_csv(recs, tmp_path / "damage.csv")
    assert read_csv(p) == recs


def test_parquet_round_trip_lossless(tmp_path):
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    recs = _sample()
    p = write_parquet(recs, tmp_path / "damage.parquet")
    assert read_parquet(p) == recs
