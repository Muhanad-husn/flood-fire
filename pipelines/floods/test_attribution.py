"""Tier-1 tests for the RQ1 flood-attribution classification (S9/W7).

Pure-logic tests over the mechanism classifier and per-AOI decomposition — no
network (GEE/CDS) or file I/O. RQ1 is a reasoning analysis, not a
`damaged_cropland_ha` output, so there is no Tier-2 gate here; these verify the
decomposition logic only. The data inputs are the human-validated S6 records,
read read-only (RQ1 never alters validation_status).

    PYTHONPATH=. python -m pytest pipelines/floods/test_attribution.py
"""

from __future__ import annotations

from pipelines.floods import attribution as A


def _chirps(aoi, pairs):
    return {aoi: [{"date": d, "precip_mm": v} for d, v in pairs]}


def _glofas(reach, pairs):
    return {reach: [{"date": d, "discharge_m3s": v} for d, v in pairs]}


def test_riverine_when_discharge_high_no_rain():
    """Euphrates June: high discharge, zero rain → riverine/transboundary."""
    hect = {"deir_ez_zor": {"2026-06-07": 16564.0}}
    ch = _chirps("deir_ez_zor", [("2026-06-07", 0.0)])
    gl = _glofas("euphrates_deir_ez_zor", [("2026-06-07", 1620.0)])
    base = {"euphrates_deir_ez_zor": 480.0}
    rows = A.classify_events(hect, ch, gl, base)
    assert len(rows) == 1
    r = rows[0]
    assert r["mechanism"] == "riverine"
    assert "transboundary" in r["source_interpretation"]
    assert r["discharge_ratio_vs_baseline"] == round(1620.0 / 480.0, 2)


def test_unexplained_when_dry_river_no_rain():
    """Hasakah June: Khabur dry + zero rain → unexplained FLAG (DEC-023 artifact)."""
    hect = {"hasakah": {"2026-06-07": 38673.0}}
    ch = _chirps("hasakah", [("2026-06-07", 0.0)])
    gl = _glofas("khabur_hasakah", [("2026-06-07", 9.2)])
    base = {"khabur_hasakah": 15.6}
    r = A.classify_events(hect, ch, gl, base)[0]
    assert r["mechanism"] == "unexplained"
    assert "FLAG" in r["source_interpretation"]


def test_rainfed_tributary_pulse_reads_as_riverine_rainfall():
    """Khabur March: high discharge, sub-threshold AOI rain → riverine but tagged rainfall."""
    hect = {"hasakah": {"2026-03-03": 32456.0}}
    ch = _chirps("hasakah", [("2026-03-03", 4.8)])  # below 10mm AOI-mean
    gl = _glofas("khabur_hasakah", [("2026-03-03", 138.3)])
    base = {"khabur_hasakah": 15.6}
    r = A.classify_events(hect, ch, gl, base)[0]
    assert r["mechanism"] == "riverine"
    assert "rain-fed tributary" in r["source_interpretation"]


def test_pluvial_when_rain_high_river_low():
    hect = {"raqqa": {"2026-04-10": 500.0}}
    ch = _chirps("raqqa", [("2026-04-09", 12.0), ("2026-04-10", 9.0)])  # >=10mm over 7d
    gl = _glofas("euphrates_raqqa", [("2026-04-10", 400.0)])  # below 2x baseline
    base = {"euphrates_raqqa": 480.0}
    r = A.classify_events(hect, ch, gl, base)[0]
    assert r["mechanism"] == "pluvial"
    assert r["source_interpretation"] == "local rainfall"


def test_mixed_when_both_high():
    hect = {"deir_ez_zor": {"2026-03-04": 100.0}}
    ch = _chirps("deir_ez_zor", [("2026-03-04", 25.0)])
    gl = _glofas("euphrates_deir_ez_zor", [("2026-03-04", 1200.0)])
    base = {"euphrates_deir_ez_zor": 480.0}
    r = A.classify_events(hect, ch, gl, base)[0]
    assert r["mechanism"] == "mixed"


def test_missing_discharge_is_not_riverine():
    """No GloFAS series (licence gap) ⇒ ratio None ⇒ falls to pluvial/unexplained, never riverine."""
    hect = {"raqqa": {"2026-06-07": 100.0}}
    ch = _chirps("raqqa", [("2026-06-07", 0.0)])
    r = A.classify_events(hect, ch, {}, {"euphrates_raqqa": 480.0})[0]
    assert r["discharge_ratio_vs_baseline"] is None
    assert r["mechanism"] == "unexplained"


def test_baseline_falls_back_when_ref_missing():
    base = A._reach_baseline(None)
    assert base["euphrates_raqqa"] == A.FALLBACK_BASELINE["transboundary"]
    assert base["khabur_hasakah"] == A.FALLBACK_BASELINE["rainfed_tributary"]


def test_baseline_from_ref_means():
    ref = _glofas("khabur_hasakah", [("2025-01-01", 10.0), ("2025-01-02", 20.0)])
    base = A._reach_baseline(ref)
    assert base["khabur_hasakah"] == 15.0  # mean of 10,20
    # reaches absent from ref fall back to documented values
    assert base["euphrates_raqqa"] == A.FALLBACK_BASELINE["transboundary"]


def test_aoi_decomposition_flags_unexplained_and_takes_peak():
    events = [
        {"aoi_id": "hasakah", "mechanism": "riverine", "flooded_cropland_ha_union": 32456.0},
        {"aoi_id": "hasakah", "mechanism": "unexplained", "flooded_cropland_ha_union": 24745.0},
        {"aoi_id": "hasakah", "mechanism": "unexplained", "flooded_cropland_ha_union": 38673.0},
    ]
    # pad the other AOIs so the loop has entries
    events += [{"aoi_id": a, "mechanism": "riverine", "flooded_cropland_ha_union": 1.0}
               for a in ("deir_ez_zor", "raqqa")]
    rows = {r["aoi_id"]: r for r in A.aoi_decomposition(events)}
    h = rows["hasakah"]
    assert h["unexplained_peak_ha"] == 38673.0   # peak, not sum
    assert h["riverine_peak_ha"] == 32456.0
    assert h["unexplained_flag"] is True
    assert h["dominant_mechanism"] == "unexplained"
