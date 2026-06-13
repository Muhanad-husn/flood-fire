"""Pipeline A — flood masks ∩ cropland → damaged_cropland_ha (docs/STRUCTURE.md §4).

Orchestrates the SAR flood detection in ``flood_mask.py`` into the shared damage
schema (§3.2). Flow:

  1. **Screen** every Sentinel-1 acquisition date in the window (cheap, coarse)
     → per-date flooded-cropland area; flag **event dates** that exceed a dry
     baseline ("auto from S1 revisits").
  2. **Export** the 30 m flood binary (full refinement) only for the selected
     event dates, via geedim tiled download (DEC-016) — cost-conscious.
  3. **Locally** clean speckle (connected-component min size), stack the event
     rasters into a per-pixel flood **frequency**, intersect with the canonical
     human-reviewed ``aois/cropland_mask.tif`` (NOT a server-side proxy), and
     compute hectares per (date, severity, mask-basis).
  4. **Emit** ``DamageRecord(phenomenon=FLOOD, validation_status=unvalidated)``.
     Severity: ``transient`` (pixel flooded on a single event date) vs
     ``persistent`` (≥2 event dates) — DEC-009. The union-vs-intersection
     sensitivity range (DEC-015) is carried in ``source_layer`` so the one
     integration contract is unchanged.
  5. **Assemble** a Tier-2 validation packet (per-AOI flood-frequency previews,
     hectare table, screening series, README pointing to GloFAS / Copernicus EMS).

Tier-2 (§6, DEC-007): every record defaults to ``unvalidated``; **no agent run
sets it to ``validated``** — a human compares against GloFAS + any EMSR flood
activation and flips the status. This session is NOT done until that gate is met.

Run:
    conda run -n f_f python pipelines/floods/cropland_flooded.py            # all AOIs
    conda run -n f_f python pipelines/floods/cropland_flooded.py --aoi hasakah
    conda run -n f_f python pipelines/floods/cropland_flooded.py --screen-only
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from clients.gee_auth import initialize  # noqa: E402
from schema.damage_schema import (  # noqa: E402
    DamageRecord, Phenomenon, ValidationStatus, write_csv, write_parquet,
)
import pipelines.floods.flood_mask as fm  # noqa: E402

CRS = "EPSG:32637"
SCALE = 30
NODATA = 255

# Event-selection parameters (DEC — recorded in tracking/DECISIONS.md).
MAX_EVENTS = 5          # cap full 30 m exports per AOI (cost-conscious)
EVENT_FLOOR_HA = 500.0  # ignore sub-noise "events" below this flooded-cropland area
MAD_K = 3.0             # event if area > median + MAD_K·MAD …
MULT_K = 1.5            # … or > MULT_K · median
MIN_COMPONENT_PX = 8    # local speckle cleanup: drop flood blobs < this (≈0.7 ha)

# Floods AOIs only (§4): Deir ez-Zor, Raqqa, Hasakah. gaul = GAUL ADM1_NAME.
AOIS = [
    {"aoi_id": "deir_ez_zor", "name": "Deir ez-Zor", "gaul": "Dayr_Az_Zor"},
    {"aoi_id": "raqqa",       "name": "Raqqa",       "gaul": "Raqqa"},
    {"aoi_id": "hasakah",     "name": "Hasakah",     "gaul": "Hassakeh"},
]

FLOODS_DIR = REPO / "pipelines" / "floods"
TILES_DIR = FLOODS_DIR / "_flood_tiles"
AOIS_DIR = REPO / "aois"
GOV_PATH = AOIS_DIR / "governorates.geojson"
MASK_PATH = AOIS_DIR / "cropland_mask.tif"
OUT_DIR = REPO / "outputs" / "floods"
PACKET_DIR = OUT_DIR / "validation_packet"

SOURCE_UNION = "S1_GRD_changedet+cropland_union"
SOURCE_INTER = "S1_GRD_changedet+cropland_intersection"
SOURCE_PERM = "JRC_GSW_permanent"


def _syria_l1(ee):
    return (ee.FeatureCollection("FAO/GAUL/2015/level1")
            .filter(ee.Filter.eq("ADM0_NAME", "Syrian Arab Republic")))


def _geom(ee, gaul):
    return _syria_l1(ee).filter(ee.Filter.eq("ADM1_NAME", gaul)).first().geometry()


# ----------------------------------------------------------------------------
# 1) screening: per-date flooded-cropland area, select event dates
# ----------------------------------------------------------------------------
def screen_aoi(ee, geom, name, aoi_id, rescreen=False):
    """Per-date flooded-cropland screen, cached to TILES_DIR (compute is dear —
    the GEE noncommercial tier throttles; a rerun reuses the cached series)."""
    cache = TILES_DIR / f"{aoi_id}_screen.json"
    if cache.exists() and not rescreen:
        print(f"  [{name}] screen cache hit ({cache.name})")
        return json.loads(cache.read_text(encoding="utf-8"))
    dates = fm.acquisition_dates(ee, geom)
    print(f"  [{name}] {len(dates)} S1 acquisition dates in window; screening ...")
    series = {}
    for d in dates:
        try:
            ha = ee.Number(fm.flooded_cropland_ha(ee, geom, d)).getInfo() or 0.0
        except Exception as exc:  # transient EE error on one date — record 0, continue
            print(f"    {d}: screen error {repr(exc)[:80]}")
            ha = 0.0
        series[d] = round(ha, 1)
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(series, indent=2), encoding="utf-8")
    return series


def select_event_dates(series):
    """Flag dates whose flooded-cropland area exceeds the dry baseline (DEC)."""
    vals = sorted(series.values())
    if not vals:
        return [], 0.0
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals]) or 0.0
    baseline = max(med + MAD_K * mad, MULT_K * med, EVENT_FLOOR_HA)
    events = [d for d, v in series.items() if v > baseline]
    events = sorted(events, key=lambda d: -series[d])[:MAX_EVENTS]
    if not events:  # nothing exceeded the floor — take the single wettest date
        top = max(series, key=lambda d: series[d])
        if series[top] > 0:
            events = [top]
    return sorted(events), round(baseline, 1)


# ----------------------------------------------------------------------------
# 2) export the 30 m flood binary for selected event dates (geedim, DEC-016)
# ----------------------------------------------------------------------------
def export_event_raster(ee, geom, date_str, out, attempts=5):
    # GEE noncommercial "Restricted Mode" caps concurrency hard — keep
    # max_requests low (=2) or geedim's parallel tile fetch trips 429s.
    import geedim  # noqa: F401 — registers .gd accessor
    img = fm.flood_binary(ee, geom, date_str, refine=True).unmask(0).toUint8()
    img = img.gd.prepareForExport(crs=CRS, scale=SCALE, region=geom,
                                  dtype="uint8", resampling="near")
    last = None
    for k in range(attempts):
        try:
            img.gd.toGeoTIFF(out, overwrite=True, nodata=NODATA,
                             max_tile_size=1, max_tile_dim=1500, max_requests=2)
            return
        except Exception as exc:
            last = exc
            print(f"    [{date_str}] export attempt {k+1}/{attempts}: {repr(exc)[:110]}")
            time.sleep(20 * (k + 1))  # longer backoff for restricted-mode 429s
    raise RuntimeError(f"flood export failed for {date_str}: {last}")


# ----------------------------------------------------------------------------
# 3) local hectare accounting: stack -> frequency -> severity -> hectares
# ----------------------------------------------------------------------------
def _clean(arr):
    """8-connected speckle cleanup: drop flood components < MIN_COMPONENT_PX."""
    from scipy import ndimage
    lab, n = ndimage.label(arr > 0, structure=[[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    if n == 0:
        return arr.astype("uint8")
    sizes = ndimage.sum(arr > 0, lab, range(1, n + 1))
    keep = {i + 1 for i, s in enumerate(sizes) if s >= MIN_COMPONENT_PX}
    import numpy as np
    return np.isin(lab, list(keep)).astype("uint8")


def process_aoi(ee, aoi, event_dates):
    """Return (records, packet_info) for one AOI from its exported event rasters."""
    import numpy as np
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.features import geometry_mask
    import geopandas as gpd

    aoi_id, name = aoi["aoi_id"], aoi["name"]
    tdir = TILES_DIR / aoi_id
    gov = gpd.read_file(GOV_PATH).to_crs(CRS)
    poly = gov.loc[gov["aoi_id"] == aoi_id, "geometry"].iloc[0]

    # Reference grid = the first event raster (all event rasters share the grid:
    # same crs/scale/region in prepareForExport).
    first = tdir / f"{event_dates[0]}.tif"
    with rasterio.open(first) as ds0:
        grid_shape, grid_transform = (ds0.height, ds0.width), ds0.transform
        px_ha = abs(grid_transform.a * grid_transform.e) / 1e4

    # canonical cropland mask resampled onto the event grid (nearest — "resample
    # the mask, don't redefine cropland", S3 handoff). value ∈ {1,2,3} = union;
    # value == 3 = intersection (DEC-015).
    with rasterio.open(MASK_PATH) as mds:
        mask_on = np.zeros(grid_shape, dtype="uint8")
        reproject(source=mds.read(1), destination=mask_on,
                  src_transform=mds.transform, src_crs=mds.crs,
                  dst_transform=grid_transform, dst_crs=CRS,
                  resampling=Resampling.nearest, src_nodata=255, dst_nodata=0)
    inside = geometry_mask([poly.__geo_interface__], out_shape=grid_shape,
                           transform=grid_transform, invert=True)
    crop_union = np.isin(mask_on, (1, 2, 3)) & inside
    crop_inter = (mask_on == 3) & inside

    # load + clean each event raster onto the shared grid
    floods = {}
    for d in event_dates:
        with rasterio.open(tdir / f"{d}.tif") as ds:
            a = ds.read(1)
            a = np.where(a == NODATA, 0, a)
        floods[d] = _clean(a)
    freq = np.sum(list(floods.values()), axis=0).astype("int16")  # 0..N events
    persistent = freq >= 2

    records, table = [], []
    for d in event_dates:
        fl = floods[d].astype(bool) & inside
        trans = fl & (freq == 1)
        pers = fl & persistent
        cells = {
            ("transient", SOURCE_UNION): (trans & crop_union).sum(),
            ("transient", SOURCE_INTER): (trans & crop_inter).sum(),
            ("persistent", SOURCE_UNION): (pers & crop_union).sum(),
            ("persistent", SOURCE_INTER): (pers & crop_inter).sum(),
        }
        for (sev, src), npx in cells.items():
            ha = round(float(npx) * px_ha, 2)
            if ha <= 0:
                continue
            records.append(DamageRecord(
                aoi_id=aoi_id, date=d, phenomenon=Phenomenon.FLOOD,
                severity_class=sev, source_layer=src, damaged_cropland_ha=ha,
                validation_status=ValidationStatus.UNVALIDATED))
            table.append({"aoi_id": aoi_id, "date": d, "severity": sev,
                          "mask_basis": src.split("+")[-1], "ha": ha})

    # permanent_excluded: 0-ha record naming the subtracted river (DEC-009).
    perm_ha = round(ee.Number(fm.permanent_cropland_ha(ee, _geom(ee, aoi["gaul"]))).getInfo() or 0.0, 1)
    records.append(DamageRecord(
        aoi_id=aoi_id, date=event_dates[0], phenomenon=Phenomenon.FLOOD,
        severity_class="permanent_excluded", source_layer=SOURCE_PERM,
        damaged_cropland_ha=0.0, validation_status=ValidationStatus.UNVALIDATED))

    packet = {"aoi_id": aoi_id, "name": name, "event_dates": event_dates,
              "freq": freq, "crop_union": crop_union, "crop_inter": crop_inter,
              "grid_transform": grid_transform, "px_ha": px_ha,
              "permanent_water_cropland_ha": perm_ha, "poly": poly}
    return records, table, packet


# ----------------------------------------------------------------------------
# 4) validation packet (Tier-2 human-review surface, §6)
# ----------------------------------------------------------------------------
def render_packet(packet):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    import geopandas as gpd

    freq = packet["freq"].astype(float)
    crop_union = packet["crop_union"]
    n = len(packet["event_dates"])
    t = packet["grid_transform"]
    h, w = freq.shape
    ext = [t.c, t.c + t.a * w, t.f + t.e * h, t.f]  # (xmin,xmax,ymin,ymax)

    # background = cropland extent (grey); overlay flood frequency on cropland
    bg = np.where(crop_union, 0.15, np.nan)
    show = np.where((freq > 0) & crop_union, freq, np.nan)

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(bg, cmap=ListedColormap(["#dcdcd2"]), extent=ext, interpolation="nearest")
    # one blue per frequency level (1..n): higher persistence = darker
    nb = max(n, 1)
    ramp = plt.get_cmap("YlGnBu")
    cmap = ListedColormap([ramp((i + 1) / (nb + 1)) for i in range(nb)])
    norm = BoundaryNorm(np.arange(0.5, nb + 1.5, 1), cmap.N)
    im = ax.imshow(show, cmap=cmap, norm=norm, extent=ext, interpolation="nearest")
    gpd.GeoSeries([packet["poly"]], crs=CRS).boundary.plot(ax=ax, color="black", linewidth=0.8)

    union_ha = float((show > 0).sum()) * packet["px_ha"]
    ax.set_title(f"{packet['name']} — flooded cropland (S1 change-detection, 30 m)\n"
                 f"{n} event date(s) · flooded cropland (union) {union_ha:,.0f} ha · "
                 f"UNVALIDATED (Tier-2 §6)")
    ax.legend(handles=[Patch(facecolor="#dcdcd2", edgecolor="k", label="cropland (union)")]
              + [Patch(facecolor=cmap(i), edgecolor="k", label=f"flooded on {i+1} date(s)")
                 for i in range(max(n, 1))], loc="lower left", fontsize=8)
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.tight_layout()
    out = PACKET_DIR / f"{packet['aoi_id']}_flood_frequency.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


# ----------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    only_aoi = None
    screen_only = "--screen-only" in args
    rescreen = "--rescreen" in args
    if "--aoi" in args:
        only_aoi = args[args.index("--aoi") + 1]

    import ee
    initialize()

    aois = [a for a in AOIS if only_aoi is None or a["aoi_id"] == only_aoi]
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PACKET_DIR.mkdir(parents=True, exist_ok=True)

    all_records, all_table, screen_rows, selected = [], [], [], {}

    # ---- screen + select event dates --------------------------------------
    for a in aois:
        geom = _geom(ee, a["gaul"])
        series = screen_aoi(ee, geom, a["name"], a["aoi_id"], rescreen=rescreen)
        events, baseline = select_event_dates(series)
        selected[a["aoi_id"]] = events
        print(f"  [{a['name']}] baseline={baseline} ha · event dates: {events}")
        for d, ha in sorted(series.items()):
            screen_rows.append({"aoi_id": a["aoi_id"], "date": d,
                                "flooded_cropland_ha_screen": ha,
                                "is_event": d in events})

    (PACKET_DIR).mkdir(parents=True, exist_ok=True)
    with (PACKET_DIR / "screening_series.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["aoi_id", "date",
                                           "flooded_cropland_ha_screen", "is_event"])
        w.writeheader(); w.writerows(screen_rows)
    print(f"  -> screening series: {PACKET_DIR / 'screening_series.csv'}")

    if screen_only:
        print("screen-only: stopping before export.")
        return

    # ---- export event rasters + local accounting --------------------------
    for a in aois:
        events = selected[a["aoi_id"]]
        if not events:
            print(f"  [{a['name']}] no event dates — skipping.")
            continue
        geom = _geom(ee, a["gaul"])
        tdir = TILES_DIR / a["aoi_id"]; tdir.mkdir(parents=True, exist_ok=True)
        for d in events:
            out = tdir / f"{d}.tif"
            if out.exists():
                print(f"  [{a['name']}] {d} raster cached, skip export")
                continue
            print(f"  [{a['name']}] exporting flood raster {d} ...")
            export_event_raster(ee, geom, d, str(out))

        records, table, packet = process_aoi(ee, a, events)
        all_records += records; all_table += table
        png = render_packet(packet)
        print(f"  [{a['name']}] {len(records)} records · "
              f"perm-water∩cropland {packet['permanent_water_cropland_ha']:,.0f} ha · {png.name}")

    if not all_records:
        print("no event records produced.")
        return

    # ---- write schema records + packet table ------------------------------
    csv_path = write_csv(all_records, OUT_DIR / "flood_damage.csv")
    write_parquet(all_records, OUT_DIR / "flood_damage.parquet")
    with (PACKET_DIR / "hectare_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["aoi_id", "date", "severity", "mask_basis", "ha"])
        w.writeheader(); w.writerows(all_table)
    write_packet_readme(selected)
    print(f"\n-> {len(all_records)} DamageRecords (all UNVALIDATED): {csv_path}")
    print(f"-> validation packet: {PACKET_DIR}")
    print("STOP: Tier-2 human validation required (vs GloFAS + any Copernicus EMS "
          "flood activation) before any downstream session consumes these records.")


def write_packet_readme(selected):
    lines = [
        "# Flood damage — Tier-2 validation packet (Session 6 / W4)",
        "",
        "**Status: UNVALIDATED.** Every `DamageRecord` in `outputs/floods/flood_damage.csv`",
        "is `validation_status=unvalidated`. Per docs/STRUCTURE.md §6 and DEC-007, a **human**",
        "must compare these flood masks against named ground truth and flip the status — no",
        "agent/Workflow run may set `validated`. The food-security layer (S8) and RQ analyses",
        "refuse to consume any record that is not `validated`.",
        "",
        "## Named ground truth to compare against (§6, PRODUCT.md §6)",
        "- **GloFAS** Euphrates discharge — the late-May 2026 surge (~2,000 m³/s vs 200–250 in",
        "  drought years; spillway gates opened first time in 30+ years, PRODUCT.md §2). GloFAS",
        "  is wired live in S9/RQ1 (CDS API); for this gate, compare event-date timing/extent",
        "  against GloFAS reporting points on the Euphrates at Deir ez-Zor / Raqqa.",
        "- **Copernicus EMS** — any rapid-mapping flood activation (EMSR) over the AOIs in the",
        "  March–June 2026 window; compare delineated flood extent against these masks.",
        "",
        "## What to review",
        "- `*_flood_frequency.png` — flooded cropland per AOI, coloured by how many event dates",
        "  each pixel was flooded (1 date = transient; ≥2 = persistent, DEC-009).",
        "- `hectare_summary.csv` — damaged_cropland_ha per (AOI, date, severity, mask basis).",
        "- `screening_series.csv` — flooded-cropland area for EVERY S1 date; `is_event` marks",
        "  the dates selected for full 30 m processing. Sanity-check that the flagged peaks match",
        "  the known April flood/hail and late-May Euphrates surge.",
        "",
        "## Method + caveats",
        "- Sentinel-1 change-detection vs a dry-season reference of the **same relative orbit**",
        "  (geometry-matched); VV/VH backscatter drop + absolute water threshold; JRC GSW",
        "  permanent water and steep slopes removed; local connected-component speckle cleanup.",
        "- **Open-water bias:** change-detection on a backscatter *drop* captures standing water;",
        "  flooded vegetation (double-bounce *raises* VV) is under-detected — optical/Dynamic",
        "  World is the confirmatory layer (§9). Treat hectares as open-water flood extent.",
        "- **Union vs intersection (DEC-015):** reported under both cropland definitions via",
        "  `source_layer` (…+cropland_union vs …+cropland_intersection) — a sensitivity range,",
        "  union ≈ headline, intersection ≈ conservative.",
        "",
        "## Selected event dates",
    ]
    for aoi_id, ev in selected.items():
        lines.append(f"- **{aoi_id}**: {', '.join(ev) if ev else '(none)'}")
    (PACKET_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
