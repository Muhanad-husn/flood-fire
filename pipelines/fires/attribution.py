"""RQ2 — fire attribution: conflict-linked vs accidental/agricultural (W8).

Overlay FIRMS/VIIRS hotspots (S7) on ACLED conflict events and test whether the
2026 crop fires concentrate near conflict and track military activity, or follow
accidental/agricultural patterns (`docs/PRODUCT.md` §5 RQ2; PAX Sentinel-2 method
the named precedent, §6). Consumes the **validated** fire detections read-only —
RQ2 is reasoning, not a `damaged_cropland_ha` output, so there is no Tier-2 gate
(§6); it never sets `validation_status`.

Data reality (the load-bearing constraint, probed 2026-06-13)
-------------------------------------------------------------
Live **ACLED Syria coverage ends 2025-06-13** — exactly one year behind the
simulated "today" (2026-06-13). So the **2026 study fire window has ZERO ACLED
events**: the conflict overlay for the validated 2026 fires **cannot be computed**.
That is a data-availability gap, not a null finding, and it is reported as such.

Per the session decision ("build + demo on the latest window"), the full method
is built and **demonstrated on the latest ACLED-covered fire season — May 1 –
Jun 13 2025** — over the same fire AOIs (Hasakah cropland; Latakia coastal),
using VIIRS *_SP archive hotspots temporally aligned to the ACLED events. The
2025 run is a **method demonstration on baseline/context data (DEC-001)**, framed
explicitly as *not* a 2026 study finding.

The analytical spine
--------------------
A bare "X% of fires within 5 km of conflict" is not defensible: both fires (on
cropland) and conflict (in inhabited belts) avoid empty desert, so they co-locate
by geography alone. RQ2 controls for that with a **cropland-restricted spatial
null**: compare each fire's distance-to-nearest-conflict against the distance from
random *cropland* locations to conflict. Fires "concentrate along frontlines" only
if they are closer to conflict than cropland is *in general*. Three lenses:

* **Spatial** — observed fire→conflict distance vs the cropland null (does fire
  cluster near conflict beyond the cropland-geography baseline?).
* **Space-time** — fraction of fires with an armed-conflict event within both
  ``COINCIDENCE_KM`` and ``±COINCIDENCE_DAYS`` (a tighter, causally-suggestive join).
* **Temporal** — daily fire counts vs daily conflict counts (Spearman), to see if
  fire activity rises with conflict activity.

Correlation in space/time is **not** proof of cause (§9): crop-burning as a tactic,
accidental ignition during fighting, and ordinary agricultural burning in a
conflict landscape are not separable from overlay geometry alone. Claims are kept
proportionate and the confounds are stated.

Run:  PYTHONPATH=. python -m pipelines.fires.attribution
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from clients.acled import ACLED_ADMIN1, fetch_events_for_aoi
from clients.firms import VIIRS_NRT, VIIRS_SP
from pipelines.fires import active_fire

_REPO = Path(__file__).resolve().parent.parent.parent
_OUT = _REPO / "outputs" / "fires" / "rq2_attribution"
_FIG_DIR = _REPO / "outputs" / "figures"
_MASK = _REPO / "aois" / "cropland_mask.tif"

PROJ_CRS = "EPSG:32637"          # metric CRS used project-wide (UTM 37N, DEC-015)

FIRE_AOIS = ("hasakah", "latakia")
# Latest ACLED-covered fire season (the demonstration window) and the 2026 study
# window (validated S7 fires; ACLED-empty — overlay not computable).
DEMO_WINDOW = ("2025-05-01", "2025-06-13")
STUDY_WINDOW = ("2026-05-01", "2026-06-12")

# ACLED event_types that represent armed conflict (vs protests/strategic notes).
ARMED_TYPES = ("Battles", "Explosions/Remote violence", "Violence against civilians")

PROX_THRESH_KM = (1.0, 2.0, 5.0, 10.0)
COINCIDENCE_KM = 5.0             # space-time join radius
COINCIDENCE_DAYS = 7            # space-time join half-window
NULL_N = 3000                    # random cropland points for the spatial null
NULL_SEED = 20260613             # fixed (Math.random unavailable; reproducible null)
CLOSER_RATIO = 0.75              # observed median ≤ 0.75× null median ⇒ "closer than chance"


# ---------------------------------------------------------------------------
# Loading: hotspots + conflict events → projected metric arrays
# ---------------------------------------------------------------------------

def _project(lons: Sequence[float], lats: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """Lon/lat (EPSG:4326) → x/y metres in PROJ_CRS (UTM 37N)."""
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:4326", PROJ_CRS, always_xy=True)
    x, y = tr.transform(np.asarray(lons, float), np.asarray(lats, float))
    return np.asarray(x, float), np.asarray(y, float)


def _to_dates(strings: Iterable[str]) -> np.ndarray:
    """ISO date strings → numpy datetime64[D] (NaT on parse failure)."""
    out = []
    for s in strings:
        try:
            out.append(np.datetime64(datetime.strptime(s[:10], "%Y-%m-%d").date(), "D"))
        except (ValueError, TypeError):
            out.append(np.datetime64("NaT"))
    return np.asarray(out, dtype="datetime64[D]")


def load_hotspots(aoi_id: str, start: str, end: str, *, sources: Iterable[str]) -> dict:
    """Cached VIIRS hotspots for an AOI/window → {x, y, dates, n} (projected)."""
    rows = active_fire._clean(active_fire.fetch(aoi_id, start, end, sources=sources))
    lons = [r["longitude"] for r in rows]
    lats = [r["latitude"] for r in rows]
    x, y = _project(lons, lats) if rows else (np.array([]), np.array([]))
    return {"x": x, "y": y,
            "dates": _to_dates(r.get("acq_date", "") for r in rows),
            "frp": np.asarray([r.get("frp", 0.0) for r in rows], float),
            "n": len(rows)}


def load_events(aoi_id: str, start: str, end: str) -> dict:
    """Cached ACLED events for an AOI/window → {x, y, dates, types, n} (projected).

    Returns ``n == 0`` cleanly when ACLED has no coverage for the window (the 2026
    case) — the caller treats that as the data-availability gap, not an error.
    """
    rows = fetch_events_for_aoi(aoi_id, start, end)
    keep = [r for r in rows
            if r.get("latitude") not in (None, "") and r.get("longitude") not in (None, "")]
    lons = [float(r["longitude"]) for r in keep]
    lats = [float(r["latitude"]) for r in keep]
    x, y = _project(lons, lats) if keep else (np.array([]), np.array([]))
    types = [r.get("event_type", "") for r in keep]
    return {"x": x, "y": y,
            "dates": _to_dates(r.get("event_date", "") for r in keep),
            "types": types, "n": len(keep)}


def _subset_armed(events: dict) -> dict:
    """Restrict an events dict to ARMED_TYPES."""
    if events["n"] == 0:
        return events
    mask = np.asarray([t in ARMED_TYPES for t in events["types"]], bool)
    return {"x": events["x"][mask], "y": events["y"][mask],
            "dates": events["dates"][mask],
            "types": [t for t, m in zip(events["types"], mask) if m],
            "n": int(mask.sum())}


# ---------------------------------------------------------------------------
# Pure-numpy distance core (hermetically testable — no I/O)
# ---------------------------------------------------------------------------

def nearest_distance_km(px: np.ndarray, py: np.ndarray,
                        qx: np.ndarray, qy: np.ndarray) -> np.ndarray:
    """For each point P, Euclidean distance (km) to the nearest point in Q.

    Returns an all-``inf`` array when Q is empty (no conflict events ⇒ no overlay).
    """
    px, py = np.asarray(px, float), np.asarray(py, float)
    if px.size == 0:
        return np.array([])
    if np.asarray(qx).size == 0:
        return np.full(px.shape, np.inf)
    dx = px[:, None] - np.asarray(qx, float)[None, :]
    dy = py[:, None] - np.asarray(qy, float)[None, :]
    return np.sqrt(dx * dx + dy * dy).min(axis=1) / 1000.0


def nearest_distance_temporal_km(px, py, pdates, qx, qy, qdates,
                                 *, max_days: int) -> np.ndarray:
    """Nearest-Q distance (km) per P, restricted to Q within ±``max_days`` of P.

    ``inf`` where no Q falls inside the temporal window (so a space-only-near but
    time-far event does not count as coincident).
    """
    px, py = np.asarray(px, float), np.asarray(py, float)
    if px.size == 0:
        return np.array([])
    qx = np.asarray(qx, float)
    out = np.full(px.shape, np.inf)
    if qx.size == 0:
        return out
    qdates = np.asarray(qdates, dtype="datetime64[D]")
    pdates = np.asarray(pdates, dtype="datetime64[D]")
    for i in range(px.size):
        dd = np.abs((qdates - pdates[i]).astype("timedelta64[D]").astype(float))
        sel = dd <= max_days
        if not sel.any():
            continue
        dx = px[i] - qx[sel]
        dy = py[i] - np.asarray(qy, float)[sel]
        out[i] = np.sqrt(dx * dx + dy * dy).min() / 1000.0
    return out


def proximity_summary(dist_km: np.ndarray,
                      thresholds: Sequence[float] = PROX_THRESH_KM) -> dict:
    """Fraction of points within each distance threshold + median distance."""
    d = np.asarray(dist_km, float)
    finite = d[np.isfinite(d)]
    out: dict[str, Any] = {"n": int(d.size),
                           "median_km": (float(np.median(finite)) if finite.size else None)}
    for t in thresholds:
        out[f"frac_within_{t:g}km"] = (float((d <= t).mean()) if d.size else None)
    return out


def coincidence_fraction(dist_temporal_km: np.ndarray, *, max_km: float = COINCIDENCE_KM) -> float | None:
    """Fraction of points with a within-window event also within ``max_km``."""
    d = np.asarray(dist_temporal_km, float)
    if d.size == 0:
        return None
    return float((d <= max_km).mean())


def daily_counts(fire_dates: np.ndarray, event_dates: np.ndarray,
                 armed_dates: np.ndarray, start: str, end: str) -> list[dict]:
    """Per-day fire / all-conflict / armed-conflict counts over [start, end]."""
    d0 = np.datetime64(start, "D")
    d1 = np.datetime64(end, "D")
    days = np.arange(d0, d1 + np.timedelta64(1, "D"), dtype="datetime64[D]")

    def _count(dates):
        dates = np.asarray(dates, dtype="datetime64[D]")
        dates = dates[~np.isnat(dates)]
        return {d: int(c) for d, c in zip(*np.unique(dates, return_counts=True))}

    fc, ec, ac = _count(fire_dates), _count(event_dates), _count(armed_dates)
    return [{"date": str(d), "n_fires": fc.get(d, 0),
             "n_conflict": ec.get(d, 0), "n_armed": ac.get(d, 0)} for d in days]


def spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Spearman rank correlation (no scipy dep). None if degenerate/constant."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if a.size < 3 or b.size < 3:
        return None

    def _rank(v):
        order = v.argsort()
        ranks = np.empty_like(order, float)
        ranks[order] = np.arange(v.size, dtype=float)
        # average ties
        _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        sums = np.zeros(cnt.size)
        np.add.at(sums, inv, ranks)
        avg = sums / cnt
        return avg[inv]

    ra, rb = _rank(a), _rank(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def event_type_composition(hot: dict, events: dict, *, max_km: float = COINCIDENCE_KM,
                           max_days: int = COINCIDENCE_DAYS) -> dict[str, int]:
    """Count, by event_type, the conflict events that are near+coincident to a fire.

    An event is counted once if any fire lies within ``max_km`` and ``±max_days``
    of it — i.e. the conflict "explained by" co-located fire activity.
    """
    out: dict[str, int] = {}
    if events["n"] == 0 or hot["n"] == 0:
        return out
    ex, ey, ed = events["x"], events["y"], events["dates"]
    for j in range(events["n"]):
        dd = np.abs((np.asarray(hot["dates"], "datetime64[D]") - ed[j]
                     ).astype("timedelta64[D]").astype(float))
        sel = dd <= max_days
        if sel.any():
            dx = ex[j] - hot["x"][sel]
            dy = ey[j] - hot["y"][sel]
            if (np.sqrt(dx * dx + dy * dy).min() / 1000.0) <= max_km:
                t = events["types"][j]
                out[t] = out.get(t, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Cropland-restricted spatial null (controls for the cropland-geography confound)
# ---------------------------------------------------------------------------

def cropland_null_distance_km(aoi_id: str, events: dict, *, n: int = NULL_N,
                              seed: int = NULL_SEED) -> np.ndarray | None:
    """Distance (km) from ``n`` random cropland pixels of an AOI to nearest conflict.

    Reads ``aois/cropland_mask.tif`` (value ∈ {1,2,3} = cropland, DEC-015), already
    in PROJ_CRS, restricts to the AOI's mosaic footprint, samples ``n`` cropland
    pixels, and measures each to the nearest event. The honest baseline for "is a
    fire closer to conflict than cropland is in general?". Returns ``None`` if the
    mask is absent (clean checkout) or no cropland pixels are found in-window.
    """
    if not _MASK.is_file() or events["n"] == 0:
        return None
    try:
        import rasterio
        from rasterio.windows import from_bounds
    except Exception:  # pragma: no cover
        return None

    # Bound the read to the AOI polygon (projected) so we don't scan all 4 AOIs.
    from clients._common import load_aois  # stdlib-JSON loader, no geopandas
    geom = load_aois()[aoi_id]["geometry"]
    coords = _polygon_coords(geom)
    lon = [c[0] for c in coords]
    lat = [c[1] for c in coords]
    px, py = _project(lon, lat)
    minx, maxx, miny, maxy = px.min(), px.max(), py.min(), py.max()

    rng = np.random.default_rng(seed)
    with rasterio.open(_MASK) as ds:
        win = from_bounds(minx, miny, maxx, maxy, ds.transform).round_offsets().round_lengths()
        arr = ds.read(1, window=win)
        wt = ds.window_transform(win)
    rows_, cols_ = np.where((arr >= 1) & (arr <= 3))
    if rows_.size == 0:
        return None
    pick = rng.choice(rows_.size, size=min(n, rows_.size), replace=False)
    xs, ys = rasterio.transform.xy(wt, rows_[pick], cols_[pick])
    return nearest_distance_km(np.asarray(xs), np.asarray(ys), events["x"], events["y"])


def _polygon_coords(geom: dict) -> list[tuple[float, float]]:
    """Flatten a GeoJSON Polygon/MultiPolygon exterior coords to a point list."""
    t = geom["type"]
    if t == "Polygon":
        return [tuple(c) for ring in geom["coordinates"] for c in ring]
    if t == "MultiPolygon":
        return [tuple(c) for poly in geom["coordinates"] for ring in poly for c in ring]
    raise ValueError(f"unsupported geometry {t}")


# ---------------------------------------------------------------------------
# Per-window analysis
# ---------------------------------------------------------------------------

def analyse_window(aoi_id: str, start: str, end: str, *, sources: Iterable[str],
                   with_null: bool = True) -> dict:
    """Full RQ2 analysis for one AOI/window. Returns a structured result dict.

    ``events['n'] == 0`` (the ACLED gap) is handled gracefully: the fire side is
    still summarised and ``conflict_available`` is False.
    """
    hot = load_hotspots(aoi_id, start, end, sources=sources)
    events = load_events(aoi_id, start, end)
    armed = _subset_armed(events)

    res: dict[str, Any] = {
        "aoi_id": aoi_id, "start": start, "end": end,
        "n_fires": hot["n"], "n_conflict": events["n"], "n_armed": armed["n"],
        "conflict_available": events["n"] > 0,
    }
    if hot["n"] == 0 or events["n"] == 0:
        res["note"] = ("no ACLED conflict events for this window — overlay not computable"
                       if events["n"] == 0 else "no VIIRS hotspots for this window")
        res["daily"] = daily_counts(hot["dates"], events["dates"], armed["dates"], start, end)
        return res

    # Spatial: observed fire→armed-conflict distance vs cropland null.
    obs = nearest_distance_km(hot["x"], hot["y"], armed["x"], armed["y"])
    res["proximity_armed"] = proximity_summary(obs)
    res["proximity_all"] = proximity_summary(
        nearest_distance_km(hot["x"], hot["y"], events["x"], events["y"]))

    if with_null:
        null = cropland_null_distance_km(aoi_id, armed)
        if null is not None and null.size:
            res["null_median_km"] = float(np.median(null[np.isfinite(null)]))
            obs_med = res["proximity_armed"]["median_km"]
            res["closer_than_cropland"] = (
                obs_med is not None and res["null_median_km"] is not None
                and obs_med <= CLOSER_RATIO * res["null_median_km"])

    # Space-time coincidence (armed conflict within COINCIDENCE_KM & ±days).
    dt = nearest_distance_temporal_km(hot["x"], hot["y"], hot["dates"],
                                      armed["x"], armed["y"], armed["dates"],
                                      max_days=COINCIDENCE_DAYS)
    res["coincidence_frac_armed"] = coincidence_fraction(dt)

    # Temporal: daily fire vs conflict, Spearman.
    daily = daily_counts(hot["dates"], events["dates"], armed["dates"], start, end)
    res["daily"] = daily
    res["spearman_fire_conflict"] = spearman([d["n_fires"] for d in daily],
                                             [d["n_conflict"] for d in daily])
    res["spearman_fire_armed"] = spearman([d["n_fires"] for d in daily],
                                          [d["n_armed"] for d in daily])
    res["composition_near_fire"] = event_type_composition(hot, events)
    return res


# ---------------------------------------------------------------------------
# Writers + figure
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _proximity_rows(results: list[dict]) -> list[dict]:
    rows = []
    for r in results:
        base = {"aoi_id": r["aoi_id"], "window": f"{r['start']}..{r['end']}",
                "n_fires": r["n_fires"], "n_armed_conflict": r["n_armed"],
                "conflict_available": r["conflict_available"]}
        pa = r.get("proximity_armed") or {}
        base.update({
            "fire_median_km_to_armed": pa.get("median_km"),
            "frac_within_1km": pa.get("frac_within_1km"),
            "frac_within_5km": pa.get("frac_within_5km"),
            "frac_within_10km": pa.get("frac_within_10km"),
            "cropland_null_median_km": r.get("null_median_km"),
            "closer_than_cropland_baseline": r.get("closer_than_cropland"),
            "coincidence_frac_armed_5km_7d": r.get("coincidence_frac_armed"),
            "spearman_fire_vs_conflict": r.get("spearman_fire_conflict"),
            "spearman_fire_vs_armed": r.get("spearman_fire_armed"),
        })
        rows.append(base)
    return rows


def _figure(demo: list[dict]) -> Path | None:
    """Per-AOI: observed fire→conflict distance CDF vs the cropland null."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    usable = [r for r in demo if r.get("proximity_armed") and r.get("n_armed", 0) > 0]
    if not usable:
        return None

    fig, axes = plt.subplots(1, len(usable), figsize=(6 * len(usable), 4.5), squeeze=False)
    for ax, r in zip(axes[0], usable):
        # Re-derive the observed distance array for the CDF (cheap recompute).
        hot = load_hotspots(r["aoi_id"], r["start"], r["end"], sources=VIIRS_SP)
        armed = _subset_armed(load_events(r["aoi_id"], r["start"], r["end"]))
        obs = nearest_distance_km(hot["x"], hot["y"], armed["x"], armed["y"])
        null = cropland_null_distance_km(r["aoi_id"], armed)
        for data, lab, col in ((obs, "fires → conflict", "#c0392b"),
                               (null, "cropland → conflict (null)", "#888888")):
            if data is None or data.size == 0:
                continue
            d = np.sort(data[np.isfinite(data)])
            ax.plot(d, np.linspace(0, 1, d.size), label=lab, color=col, lw=2)
        ax.set_title(f"{r['aoi_id']} — 2025 demo\n{r['n_fires']} fires, {r['n_armed']} armed events",
                     fontsize=10, loc="left")
        ax.set_xlabel("distance to nearest armed-conflict event (km)")
        ax.set_ylabel("cumulative fraction")
        ax.set_xlim(0, 40)
        ax.legend(fontsize=8, loc="lower right")
    fig.suptitle("RQ2 — fire→conflict proximity vs cropland-geography null (2025 demonstration window)",
                 fontsize=11)
    try:
        from viz.style import caveat_footer
        caveat_footer(fig, "Method demonstration on 2025 baseline/context data (DEC-001). "
                           "Spatial/temporal co-location is not proof of cause (§9). "
                           "ACLED has no 2026 coverage — the 2026 study overlay is not computable.")
    except Exception:
        fig.tight_layout()
    _FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = _FIG_DIR / "w8_rq2_fire_conflict.png"
    fig.savefig(out, dpi=140)
    import matplotlib.pyplot as plt2  # noqa
    plt2.close(fig)
    return out


def _verdict(r: dict) -> str:
    """One-line proportionate characterisation for a demo AOI."""
    if not r.get("conflict_available") or r.get("n_armed", 0) == 0:
        return "no armed-conflict events to compare against"
    closer = r.get("closer_than_cropland")
    coinc = r.get("coincidence_frac_armed")
    sp = r.get("spearman_fire_armed")
    parts = []
    if closer is True:
        parts.append("fires sit **closer** to armed conflict than cropland does in general "
                     "(spatial association beyond the cropland-geography baseline)")
    elif closer is False:
        parts.append("fires are **no closer** to armed conflict than cropland is in general "
                     "(co-location explained by shared geography, not a frontline signal)")
    if coinc is not None:
        parts.append(f"{coinc:.0%} of fires have an armed event within "
                     f"{COINCIDENCE_KM:g} km & ±{COINCIDENCE_DAYS} d")
    if sp is not None:
        parts.append(f"daily fire–armed-conflict rank correlation ρ={sp:+.2f}")
    return "; ".join(parts) if parts else "insufficient signal"


def _write_finding(demo: list[dict], study: list[dict], fig: Path | None) -> None:
    from textwrap import dedent
    L: list[str] = []
    L.append("# RQ2 — Fire attribution: conflict-linked vs accidental/agricultural\n")
    L.append("_Generated by `pipelines/fires/attribution.py`. Consumes the validated S7 "
             "fire detections read-only (§6); RQ2 is reasoning, not a `damaged_cropland_ha` "
             "output, so there is no Tier-2 gate. Proportionate claims (§9): spatial/temporal "
             "co-location of fire and conflict is **not** proof that conflict caused the fire._\n")

    L.append("## The data-availability constraint (read first)\n")
    L.append(dedent("""\
        **Live ACLED Syria coverage ends 2025-06-13 — exactly one year behind the simulated
        "today" (2026-06-13).** The **2026 study fire window therefore has ZERO ACLED conflict
        events**, so the conflict overlay for the human-validated 2026 fires **cannot be
        computed**. This is a *data-availability gap*, not a finding of "no linkage".

        Per the session decision, the full method is **built and demonstrated on the latest
        ACLED-covered fire season — 1 May – 13 Jun 2025** — over the same fire AOIs, using
        VIIRS `*_SP` archive hotspots aligned in time to the ACLED events. **The 2025 run is a
        method demonstration on baseline/context data ([[DEC-001]]); it is not a 2026 study
        finding.** When ACLED ingests 2026 Syria data, re-running over `STUDY_WINDOW` produces
        the actual study result with no code change.
        """))

    L.append("## 2026 study window — fire signal (overlay pending ACLED 2026)\n")
    L.append("| AOI | window | VIIRS fires | ACLED events | overlay |")
    L.append("|---|---|---|---|---|")
    for r in study:
        L.append(f"| {r['aoi_id']} | {r['start']}..{r['end']} | {r['n_fires']} | "
                 f"{r['n_conflict']} | {'—' if not r['conflict_available'] else 'computed'} "
                 f"{'(ACLED gap)' if not r['conflict_available'] else ''} |")
    L.append("\nThe validated 2026 cropland-fire signal (S7) is real — **Hasakah ≈ 3,758 ha "
             "burned cropland**, Latakia ≈ 1 ha (July peak in the simulated future). Its "
             "conflict attribution simply awaits ACLED 2026 coverage.\n")

    L.append("## 2025 demonstration — method on the latest covered window\n")
    L.append("Distances are to the nearest **armed-conflict** event "
             f"({', '.join(ARMED_TYPES)}); the **null** is the distance from random *cropland* "
             "pixels (DEC-015) to the same events — the honest baseline that controls for "
             "fires and conflict both concentrating in the inhabited/cropland belt.\n")
    L.append("| AOI | fires | armed events | fire median km | cropland null median km | "
             "closer than cropland? | coincident (5km,±7d) | ρ(fire,armed/day) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in demo:
        pa = r.get("proximity_armed") or {}
        med = pa.get("median_km")
        nullm = r.get("null_median_km")
        L.append(
            f"| {r['aoi_id']} | {r['n_fires']} | {r['n_armed']} | "
            f"{med:.1f} | {nullm:.1f} | "
            f"{'**yes**' if r.get('closer_than_cropland') else 'no'} | "
            f"{(r.get('coincidence_frac_armed') or 0):.0%} | "
            f"{r.get('spearman_fire_armed'):+.2f} |"
            if med is not None and nullm is not None else
            f"| {r['aoi_id']} | {r['n_fires']} | {r['n_armed']} | n/a | n/a | n/a | n/a | n/a |")
    L.append("")
    for r in demo:
        L.append(f"- **{r['aoi_id']} (2025 demo):** {_verdict(r)}.")
    L.append("")

    L.append("## Interpretation & confidence\n")
    L.append(dedent(f"""\
        - **Method works end-to-end — HIGH confidence.** The proximity, space-time
          coincidence, daily-correlation, and cropland-null lenses all compute over real
          temporally-aligned data in the 2025 demonstration. The pipeline is ready for the
          2026 study window the moment ACLED coverage reaches it.
        - **2026 conflict linkage — NOT YET ASSESSABLE.** No ACLED 2026 data ⇒ no overlay.
          State this as a gap; do **not** infer "fires are unrelated to conflict".
        - **What the 2025 demo can and cannot say (§9).** The cropland-restricted null is the
          load-bearing control: a raw "fraction within 5 km" looks alarming only because fire
          and conflict share the same inhabited geography. Even where fires test *closer* than
          the cropland baseline, that is **spatial association, not causation** — accidental
          ignition during fighting, crop-burning as a tactic, and ordinary agricultural burning
          in a conflict landscape are not separable by overlay geometry. PAX's Sentinel-2
          method (PRODUCT §6) is the named precedent for the descriptive overlay, not for a
          causal claim.
        """))

    L.append("## Flags surfaced for the human (per CLAUDE.md — not silently resolved)\n")
    L.append(dedent("""\
        - **2026 RQ2 cannot be completed against real conflict data until ACLED ingests 2026
          Syria events** (currently max `event_date` = 2025-06-13). S12 should record this as a
          known data-availability gap in the verification pass; the method + demo stand, the
          2026 study overlay is deferred.
        - The 2025 demonstration uses **VIIRS `*_SP` archive hotspots over 2025 cropland**,
          which are **baseline/context ([[DEC-001]]), not study `DamageRecord`s** — they are
          not emitted to the schema and carry no `validation_status`.
        """))

    L.append("## Caveats\n")
    L.append(dedent("""\
        - ACLED events are point-geocoded with variable precision (some to town centroids);
          "distance to nearest conflict" inherits that uncertainty. ACLED is **proprietary** —
          cited and cached locally, never republished raw.
        - "Frontline" is not a line in ACLED; it is approximated by the distribution of armed
          events (Battles / Explosions-Remote violence / Violence against civilians).
        - VIIRS detects active fire, not fire *cause*; the dNBR/cropland linkage to damage is
          the S7 product, and the DEC-031 near-fire confirmation already discriminates fire
          from harvest there. RQ2 adds the conflict dimension descriptively.
        - The cropland null samples the DEC-015 union mask within each AOI's footprint; a fixed
          seed makes it reproducible. The 0.75× "closer" rule is an analytical convention, not
          a significance test.
        - Conflict-zone, politically sensitive subject — every statement is kept proportionate
          and sourced; no causal attribution exceeds the overlay evidence.
        """))
    if fig:
        rel = fig.relative_to(_REPO).as_posix()
        L.append(f"\n_Figure: `{rel}` (fire→conflict vs cropland-null distance CDF, "
                 "2025 demo; PNG gitignored per [[DEC-008]], regenerated from code)._\n")

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "RQ2_FINDING.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run() -> dict[str, Any]:
    """Run the 2025 demonstration + the 2026 study-window check; write all outputs."""
    _OUT.mkdir(parents=True, exist_ok=True)

    demo = [analyse_window(aoi, *DEMO_WINDOW, sources=VIIRS_SP) for aoi in FIRE_AOIS]
    study = [analyse_window(aoi, *STUDY_WINDOW, sources=VIIRS_NRT, with_null=False)
             for aoi in FIRE_AOIS]

    _write_csv(_OUT / "proximity_summary.csv", _proximity_rows(demo + study))
    for r in demo:
        if r.get("daily"):
            _write_csv(_OUT / f"daily_counts_{r['aoi_id']}_2025.csv", r["daily"])
        comp = r.get("composition_near_fire") or {}
        if comp:
            _write_csv(_OUT / f"conflict_types_near_fire_{r['aoi_id']}_2025.csv",
                       [{"event_type": k, "n_near_fire": v} for k, v in
                        sorted(comp.items(), key=lambda kv: -kv[1])])

    fig = _figure(demo)
    _write_finding(demo, study, fig)
    return {"demo": demo, "study": study, "figure": str(fig) if fig else None}


if __name__ == "__main__":
    res = run()
    print("RQ2 attribution written to", _OUT)
    print("figure:", res["figure"])
    for r in res["study"]:
        print(f"  STUDY {r['aoi_id']} {r['start']}..{r['end']}: "
              f"{r['n_fires']} fires, {r['n_conflict']} ACLED events"
              + ("  [FLAG] ACLED gap (overlay not computable)" if not r["conflict_available"] else ""))
    for r in res["demo"]:
        print(f"  DEMO  {r['aoi_id']} {r['start']}..{r['end']}: {_verdict(r)}")
