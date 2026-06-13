"""Tier-1 tests for the RQ2 fire–conflict attribution core (S10/W8).

Pure-numpy logic tests over the distance/proximity/coincidence/temporal helpers —
no network (FIRMS/ACLED), no raster, no file I/O. RQ2 is a reasoning analysis, not
a `damaged_cropland_ha` output, so there is no Tier-2 gate; these verify the
overlay maths only. The real inputs are the validated S7 detections + ACLED events,
read read-only (RQ2 never alters validation_status).

    PYTHONPATH=. python -m pytest pipelines/fires/test_attribution.py
"""

from __future__ import annotations

import numpy as np

from pipelines.fires import attribution as A


# A handy 1 km grid in projected metres (so distances are exact and readable).
def _km(*vals):
    return np.asarray([v * 1000.0 for v in vals], float)


def _dates(*iso):
    return np.asarray([np.datetime64(d, "D") for d in iso], dtype="datetime64[D]")


# --- nearest_distance_km ------------------------------------------------------

def test_nearest_distance_basic():
    # one fire at (0,0); conflicts at 3km and 5km → nearest 3km.
    d = A.nearest_distance_km(_km(0), _km(0), _km(3, 5), _km(0, 0))
    assert np.isclose(d[0], 3.0)


def test_nearest_distance_empty_conflict_is_inf():
    d = A.nearest_distance_km(_km(0, 1), _km(0, 0), np.array([]), np.array([]))
    assert d.shape == (2,) and np.isinf(d).all()


def test_nearest_distance_empty_points_is_empty():
    d = A.nearest_distance_km(np.array([]), np.array([]), _km(0), _km(0))
    assert d.size == 0


# --- temporal nearest ---------------------------------------------------------

def test_temporal_excludes_out_of_window_events():
    # fire on Jun-01; a near event (1km) on Jun-20 (out of ±7d) and a far event
    # (10km) on Jun-03 (in window). Within ±7d only the far one counts → 10km.
    px, py, pd = _km(0), _km(0), _dates("2025-06-01")
    qx, qy = _km(1, 10), _km(0, 0)
    qd = _dates("2025-06-20", "2025-06-03")
    d = A.nearest_distance_temporal_km(px, py, pd, qx, qy, qd, max_days=7)
    assert np.isclose(d[0], 10.0)


def test_temporal_inf_when_no_event_in_window():
    px, py, pd = _km(0), _km(0), _dates("2025-06-01")
    qx, qy, qd = _km(1), _km(0), _dates("2025-07-15")
    d = A.nearest_distance_temporal_km(px, py, pd, qx, qy, qd, max_days=7)
    assert np.isinf(d[0])


# --- proximity summary --------------------------------------------------------

def test_proximity_summary_fractions_and_median():
    dist = np.array([0.5, 2.0, 6.0, 20.0])  # km
    s = A.proximity_summary(dist, thresholds=(1.0, 5.0))
    assert s["n"] == 4
    assert np.isclose(s["frac_within_1km"], 0.25)
    assert np.isclose(s["frac_within_5km"], 0.5)
    assert np.isclose(s["median_km"], (2.0 + 6.0) / 2)


def test_proximity_summary_ignores_inf_in_median():
    dist = np.array([1.0, 3.0, np.inf])
    s = A.proximity_summary(dist, thresholds=(5.0,))
    assert np.isclose(s["median_km"], 2.0)        # median of finite {1,3}
    assert np.isclose(s["frac_within_5km"], 2 / 3)  # inf counts in the denominator


# --- coincidence --------------------------------------------------------------

def test_coincidence_fraction_uses_radius():
    dt = np.array([1.0, 4.9, 5.1, np.inf])
    assert np.isclose(A.coincidence_fraction(dt, max_km=5.0), 0.5)


def test_coincidence_none_when_empty():
    assert A.coincidence_fraction(np.array([])) is None


# --- daily counts -------------------------------------------------------------

def test_daily_counts_aligns_dates():
    fires = _dates("2025-05-01", "2025-05-01", "2025-05-03")
    events = _dates("2025-05-02", "2025-05-03")
    armed = _dates("2025-05-03")
    rows = A.daily_counts(fires, events, armed, "2025-05-01", "2025-05-03")
    assert [r["date"] for r in rows] == ["2025-05-01", "2025-05-02", "2025-05-03"]
    assert rows[0]["n_fires"] == 2 and rows[0]["n_conflict"] == 0
    assert rows[2]["n_fires"] == 1 and rows[2]["n_conflict"] == 1 and rows[2]["n_armed"] == 1


# --- spearman -----------------------------------------------------------------

def test_spearman_perfect_monotonic():
    assert np.isclose(A.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)


def test_spearman_anticorrelated():
    assert np.isclose(A.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)


def test_spearman_constant_is_none():
    assert A.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None


def test_spearman_too_short_is_none():
    assert A.spearman([1, 2], [3, 4]) is None


# --- event-type composition ---------------------------------------------------

def test_event_type_composition_counts_near_coincident():
    # fire at (0,0) on Jun-01. Two events: a "Battles" 2km away Jun-02 (counts),
    # a "Protests" 2km away but Jun-30 (out of window → not counted).
    hot = {"n": 1, "x": _km(0), "y": _km(0), "dates": _dates("2025-06-01")}
    events = {"n": 2, "x": _km(2, 2), "y": _km(0, 0),
              "dates": _dates("2025-06-02", "2025-06-30"),
              "types": ["Battles", "Protests"]}
    comp = A.event_type_composition(hot, events, max_km=5.0, max_days=7)
    assert comp == {"Battles": 1}


# --- armed subset -------------------------------------------------------------

def test_subset_armed_filters_types():
    events = {"n": 3, "x": _km(0, 1, 2), "y": _km(0, 0, 0),
              "dates": _dates("2025-06-01", "2025-06-02", "2025-06-03"),
              "types": ["Battles", "Protests", "Violence against civilians"]}
    armed = A._subset_armed(events)
    assert armed["n"] == 2
    assert set(armed["types"]) == {"Battles", "Violence against civilians"}


def test_subset_armed_empty_passthrough():
    empty = {"n": 0, "x": np.array([]), "y": np.array([]),
             "dates": np.array([], dtype="datetime64[D]"), "types": []}
    assert A._subset_armed(empty)["n"] == 0


# --- polygon coord flattening (null-model helper) -----------------------------

def test_polygon_coords_polygon_and_multipolygon():
    poly = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    assert (0, 0) in A._polygon_coords(poly) and (1, 1) in A._polygon_coords(poly)
    multi = {"type": "MultiPolygon",
             "coordinates": [[[[0, 0], [1, 0], [0, 1], [0, 0]]],
                             [[[2, 2], [3, 2], [2, 3], [2, 2]]]]}
    coords = A._polygon_coords(multi)
    assert (2, 2) in coords and len(coords) == 8
