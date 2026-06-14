"""Tier-1 tests for RQ3 — descriptive control-area overlay (W9, DEC-005).

Covers the zone mapping (single / spanning / out-of-scope), the descriptive
tabulation, and the validated-only gate. All hermetic (synthetic geojson + records).
RQ3 is descriptive only: these tests check *structure*, never a differential.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schema.damage_schema import DamageRecord, Phenomenon, ValidationStatus, write_csv
from analysis import control_differential as cd


def _rec(aoi, date, sev, src, ha, phenom=Phenomenon.FLOOD, status=ValidationStatus.VALIDATED):
    return DamageRecord(aoi, date, phenom, sev, src, ha, status)


def _zone_geojson(path: Path, features):
    """features = list of (aoi_id, indicative_admin). Geometry is a dummy point box."""
    geo = {"type": "FeatureCollection", "features": []}
    for aoi, admin in features:
        geo["features"].append({
            "type": "Feature",
            "properties": {"aoi_id": aoi, "indicative_admin": admin, "indicative": True},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
        })
    path.write_text(json.dumps(geo), encoding="utf-8")


# --- zone mapping -------------------------------------------------------------

def test_zone_map_single_and_spanning(tmp_path):
    p = tmp_path / "control.geojson"
    _zone_geojson(p, [
        ("deir_ez_zor", "former_AANES"), ("deir_ez_zor", "government"),
        ("raqqa", "former_AANES"), ("latakia", "government"),
    ])
    zm = cd.load_zone_map(p)
    assert zm["raqqa"] == ("former_AANES",)
    assert zm["latakia"] == ("government",)
    assert zm["deir_ez_zor"] == ("former_AANES", "government")  # spans, sorted


def test_zone_label_single_vs_spanning():
    assert cd.zone_label(("former_AANES",)) == "former_AANES (indicative)"
    spanning = cd.zone_label(("former_AANES", "government"))
    assert "spans" in spanning and "unapportioned" in spanning


# --- descriptive overlay ------------------------------------------------------

def _zone_map():
    return {
        "deir_ez_zor": ("former_AANES", "government"),
        "raqqa": ("former_AANES",),
        "hasakah": ("former_AANES",),
        "latakia": ("government",),
    }


def test_build_overlay_tags_in_and_out_of_scope():
    u = "S1_GRD_changedet+cropland_union"
    records = [
        _rec("raqqa", "2026-06-07", "persistent", u, 1000.0),
        _rec("deir_ez_zor", "2026-06-07", "persistent", u, 500.0),
        # idlib is a national fire-only gov — outside control-area coverage
        _rec("idlib", "2026-05-01/2026-06-12", "low", "S2_dNBR", 200.0, phenom=Phenomenon.FIRE),
    ]
    rows = cd.build_overlay(records, zone_map=_zone_map())
    by_aoi = {(r.aoi_id, r.phenomenon): r for r in rows}
    assert by_aoi[("raqqa", "flood")].in_scope is True
    assert by_aoi[("raqqa", "flood")].indicative_zone == "former_AANES (indicative)"
    assert "spans" in by_aoi[("deir_ez_zor", "flood")].indicative_zone
    assert by_aoi[("idlib", "fire")].in_scope is False
    assert by_aoi[("idlib", "fire")].indicative_zone == cd._OUT_OF_SCOPE


def test_summarise_by_zone_groups_descriptively():
    u = "S1_GRD_changedet+cropland_union"
    records = [
        _rec("raqqa", "2026-06-07", "persistent", u, 1000.0),
        _rec("hasakah", "2026-06-07", "persistent", u, 2000.0),
        _rec("idlib", "2026-05-01/2026-06-12", "low", "S2_dNBR", 200.0, phenom=Phenomenon.FIRE),
    ]
    rows = cd.build_overlay(records, zone_map=_zone_map())
    summ = {z["indicative_zone"]: z for z in cd.summarise_by_zone(rows)}
    # raqqa + hasakah both former_AANES -> their flood ha sum in one row
    assert summ["former_AANES (indicative)"]["flood_ha_headline_union"] == 3000.0
    assert summ["former_AANES (indicative)"]["aois"] == "hasakah, raqqa"
    assert summ[cd._OUT_OF_SCOPE]["fire_ha_headline_union"] == 200.0


def test_overlay_skips_zero_headline_aoi():
    # An AOI whose damage aggregates to 0 ha (e.g. fully permanent_excluded) is omitted.
    u = "S1_GRD_changedet+cropland_union"
    records = [_rec("raqqa", "2026-03-02", "permanent_excluded", "JRC_GSW_permanent", 0.0)]
    rows = cd.build_overlay(records, zone_map=_zone_map())
    assert rows == []


# --- validated-only gate ------------------------------------------------------

def test_load_validated_records_refuses_unvalidated(tmp_path):
    flood = tmp_path / "flood.csv"
    write_csv([
        _rec("raqqa", "2026-06-07", "persistent", "S1_GRD_changedet+cropland_union", 100.0,
             status=ValidationStatus.UNVALIDATED),
    ], flood)
    with pytest.raises(Exception):  # ValidationGateError (re-exported from food_security)
        cd.load_validated_records(flood_csv=flood, fire_csv=tmp_path / "none.csv")
