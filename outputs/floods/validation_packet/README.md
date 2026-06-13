# Flood damage — Tier-2 validation packet (Session 6 / W4)

**Status: UNVALIDATED.** Every `DamageRecord` in `outputs/floods/flood_damage.csv`
is `validation_status=unvalidated`. Per docs/STRUCTURE.md §6 and DEC-007, a **human**
must compare these flood masks against named ground truth and flip the status — no
agent/Workflow run may set `validated`. The food-security layer (S8) and RQ analyses
refuse to consume any record that is not `validated`.

## Named ground truth to compare against (§6, PRODUCT.md §6)
- **GloFAS** Euphrates discharge — the late-May 2026 surge (~2,000 m³/s vs 200–250 in
  drought years; spillway gates opened first time in 30+ years, PRODUCT.md §2). GloFAS
  is wired live in S9/RQ1 (CDS API); for this gate, compare event-date timing/extent
  against GloFAS reporting points on the Euphrates at Deir ez-Zor / Raqqa.
- **Copernicus EMS** — any rapid-mapping flood activation (EMSR) over the AOIs in the
  March–June 2026 window; compare delineated flood extent against these masks.

## What to review
- `*_flood_frequency.png` — flooded cropland per AOI, coloured by how many event dates
  each pixel was flooded (1 date = transient; ≥2 = persistent, DEC-009).
- `hectare_summary.csv` — damaged_cropland_ha per (AOI, date, severity, mask basis).
- `screening_series.csv` — flooded-cropland area for EVERY S1 date; `is_event` marks
  the dates selected for full 30 m processing. Sanity-check that the flagged peaks match
  the known April flood/hail and late-May Euphrates surge.

## Method + caveats
- Sentinel-1 change-detection vs a dry-season reference of the **same relative orbit**
  (geometry-matched); VV/VH backscatter drop + absolute water threshold; JRC GSW
  permanent water and steep slopes removed; local connected-component speckle cleanup.
- **Open-water bias:** change-detection on a backscatter *drop* captures standing water;
  flooded vegetation (double-bounce *raises* VV) is under-detected — optical/Dynamic
  World is the confirmatory layer (§9). Treat hectares as open-water flood extent.
- **Union vs intersection (DEC-015):** reported under both cropland definitions via
  `source_layer` (…+cropland_union vs …+cropland_intersection) — a sensitivity range,
  union ≈ headline, intersection ≈ conservative.

## Selected event dates
- **deir_ez_zor**: 2026-03-04, 2026-06-02, 2026-06-03, 2026-06-06, 2026-06-07
- **raqqa**: 2026-03-02, 2026-05-31, 2026-06-06, 2026-06-07, 2026-06-08
- **hasakah**: 2026-03-03, 2026-03-04, 2026-06-02, 2026-06-03, 2026-06-07
