"""Tier-1 tests for the food-security impact layer (docs/STRUCTURE.md §6, §3.4).

Covers the hard validation gate (refuses non-validated records), the temporal
double-count avoidance for floods, exact severity summation for fires, and the
hectares -> production-loss arithmetic. All hermetic (synthetic records / tmp_path).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from schema.damage_schema import DamageRecord, Phenomenon, ValidationStatus, write_csv
from food_security import impact_layer as il


# --- the §6 validation gate ---------------------------------------------------

def _rec(aoi, date, sev, src, ha, status=ValidationStatus.VALIDATED, phenom=Phenomenon.FLOOD):
    return DamageRecord(aoi, date, phenom, sev, src, ha, status)


def test_gate_passes_validated_records():
    recs = [_rec("hasakah", "2026-06-07", "transient", "S1_GRD_changedet+cropland_union", 100.0)]
    assert il.gate_records(recs) == recs


def test_gate_refuses_unvalidated_record():
    recs = [
        _rec("hasakah", "2026-06-07", "transient", "S1_GRD_changedet+cropland_union", 100.0),
        _rec("raqqa", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_union", 50.0,
             status=ValidationStatus.UNVALIDATED),
    ]
    with pytest.raises(il.ValidationGateError):
        il.gate_records(recs)


def test_gate_refuses_rejected_record():
    recs = [_rec("raqqa", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_union", 50.0,
                 status=ValidationStatus.REJECTED)]
    with pytest.raises(il.ValidationGateError):
        il.gate_records(recs)


def test_gate_non_strict_drops_instead_of_raising():
    recs = [
        _rec("hasakah", "2026-06-07", "transient", "S1_GRD_changedet+cropland_union", 100.0),
        _rec("raqqa", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_union", 50.0,
             status=ValidationStatus.UNVALIDATED),
    ]
    kept = il.gate_records(recs, strict=False)
    assert len(kept) == 1 and kept[0].aoi_id == "hasakah"


# --- flood temporal aggregation (no cross-date double-count) -------------------

def test_flood_peak_is_worst_single_date_not_sum():
    # Same AOI, two event dates. Peak-date total must be the larger single date,
    # never the sum across dates (which would double-count persistent pixels).
    u = "S1_GRD_changedet+cropland_union"
    recs = [
        _rec("hasakah", "2026-06-02", "transient", u, 1000.0),
        _rec("hasakah", "2026-06-02", "persistent", u, 2000.0),   # date total 3000
        _rec("hasakah", "2026-06-07", "transient", u, 500.0),
        _rec("hasakah", "2026-06-07", "persistent", u, 5000.0),   # date total 5500 -> peak
    ]
    agg = il.aggregate_floods(recs)
    assert agg["hasakah"].ha_headline == 5500.0          # peak date, not 8500 sum
    # season-distinct = Σ transient (1000+500) + peak persistent (5000) = 6500
    assert agg["hasakah"].ha_season_ref == 6500.0


def test_flood_union_vs_intersection_split_by_source_layer():
    u = "S1_GRD_changedet+cropland_union"
    i = "S1_GRD_changedet+cropland_intersection"
    recs = [
        _rec("raqqa", "2026-06-07", "persistent", u, 30000.0),
        _rec("raqqa", "2026-06-07", "persistent", i, 500.0),
    ]
    agg = il.aggregate_floods(recs)
    assert agg["raqqa"].ha_headline == 30000.0
    assert agg["raqqa"].ha_low == 500.0


def test_flood_permanent_excluded_ignored():
    u = "S1_GRD_changedet+cropland_union"
    recs = [
        _rec("raqqa", "2026-03-02", "transient", u, 100.0),
        _rec("raqqa", "2026-03-02", "permanent_excluded", "JRC_GSW_permanent", 0.0),
    ]
    agg = il.aggregate_floods(recs)
    assert agg["raqqa"].ha_headline == 100.0


# --- fire severity summation (exact, single window) ---------------------------

def test_fire_sums_severity_classes(tmp_path):
    recs = [
        _rec("hasakah", "2026-05-01/2026-06-12", "low", "S2_dNBR", 1335.0, phenom=Phenomenon.FIRE),
        _rec("hasakah", "2026-05-01/2026-06-12", "moderate_low", "S2_dNBR", 1569.0, phenom=Phenomenon.FIRE),
        _rec("hasakah", "2026-05-01/2026-06-12", "high", "S2_dNBR", 84.0, phenom=Phenomenon.FIRE),
    ]
    agg = il.aggregate_fires(recs, sensitivity_csv=tmp_path / "missing.csv")
    assert agg["hasakah"].ha_headline == 1335.0 + 1569.0 + 84.0


def test_fire_intersection_from_sensitivity_table_2026_study_only(tmp_path):
    sens = tmp_path / "sens.csv"
    with sens.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["aoi_id", "window", "date", "severity_class",
                                           "ha_union", "ha_intersection", "is_study"])
        w.writeheader()
        w.writerow({"aoi_id": "hasakah", "window": "2026", "date": "x", "severity_class": "low",
                    "ha_union": "1335", "ha_intersection": "900", "is_study": "True"})
        w.writerow({"aoi_id": "hasakah", "window": "2026", "date": "x", "severity_class": "high",
                    "ha_union": "84", "ha_intersection": "78", "is_study": "True"})
        # 2025 anchor row must be excluded (DEC-001)
        w.writerow({"aoi_id": "latakia", "window": "2025_emsr811", "date": "x", "severity_class": "low",
                    "ha_union": "13", "ha_intersection": "7", "is_study": "False"})
    recs = [_rec("hasakah", "2026-05-01/2026-06-12", "low", "S2_dNBR", 1335.0, phenom=Phenomenon.FIRE)]
    agg = il.aggregate_fires(recs, sensitivity_csv=sens)
    assert agg["hasakah"].ha_low == 900.0 + 78.0  # 2026 study rows only


# --- production-loss arithmetic + end-to-end ----------------------------------

def test_compute_impact_loss_arithmetic(tmp_path):
    # Synthetic baseline: yield = 200 t / 1000 ha = 0.2 t/ha.
    baseline = tmp_path / "baseline.csv"
    with baseline.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["gaul_adm1", "aoi_id", "is_study_aoi",
                                           "cropland_ha", "cropland_share", "cereal_production_2025_t"])
        w.writeheader()
        w.writerow({"gaul_adm1": "Hassakeh", "aoi_id": "hasakah", "is_study_aoi": "True",
                    "cropland_ha": "1000", "cropland_share": "1.0", "cereal_production_2025_t": "200"})

    flood = tmp_path / "flood.csv"
    write_csv([
        _rec("hasakah", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_union", 100.0),
        _rec("hasakah", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_intersection", 10.0),
    ], flood)
    fire = tmp_path / "fire.csv"
    write_csv([
        _rec("hasakah", "2026-05-01/2026-06-12", "low", "S2_dNBR", 50.0, phenom=Phenomenon.FIRE),
    ], fire)

    rows = il.compute_impact(flood_csv=flood, fire_csv=fire, baseline_csv=baseline,
                             sensitivity_csv=tmp_path / "none.csv")
    by = {r.phenomenon: r for r in rows}
    # flood: 100 ha × 0.2 t/ha = 20 t; 20/200 = 10% of baseline
    assert by["flood"].production_loss_t_headline == 20.0
    assert by["flood"].loss_pct_of_baseline_headline == 10.0
    assert by["flood"].production_loss_t_low == 2.0       # 10 ha × 0.2
    # fire: 50 ha × 0.2 = 10 t
    assert by["fire"].production_loss_t_headline == 10.0


def test_compute_impact_refuses_unvalidated_csv(tmp_path):
    baseline = tmp_path / "baseline.csv"
    with baseline.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["gaul_adm1", "aoi_id", "is_study_aoi",
                                           "cropland_ha", "cropland_share", "cereal_production_2025_t"])
        w.writeheader()
        w.writerow({"gaul_adm1": "Hassakeh", "aoi_id": "hasakah", "is_study_aoi": "True",
                    "cropland_ha": "1000", "cropland_share": "1.0", "cereal_production_2025_t": "200"})
    flood = tmp_path / "flood.csv"
    write_csv([
        _rec("hasakah", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_union", 100.0,
             status=ValidationStatus.UNVALIDATED),
    ], flood)
    with pytest.raises(il.ValidationGateError):
        il.compute_impact(flood_csv=flood, fire_csv=tmp_path / "none.csv",
                          baseline_csv=baseline, sensitivity_csv=tmp_path / "none.csv")


def test_pressure_label_bands():
    assert il.pressure_label(0.5) == "marginal"
    assert il.pressure_label(3.0) == "moderate incremental stress"
    assert il.pressure_label(10.0) == "significant incremental stress"
    assert il.pressure_label(25.0) == "severe incremental stress"
