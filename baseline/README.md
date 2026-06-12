# baseline/ — 2025 drought reference

Per `docs/STRUCTURE.md` §3.3. Reference layers computed **once**, not per run. All
2026 damage is expressed relative to this baseline. **Baseline/context ONLY** —
pre-2026 data is never the subject of analysis (DEC-001).

Built by `baseline/build_baseline.py` (GEE via `clients.gee_auth`, service account
DEC-012). Run any subset: `conda run -n f_f python baseline/build_baseline.py
{rainfall|ndvi|production|all}`.

## Contents (produced in W2 / S4)

### `rainfall_deficit.csv` — CHIRPS rainfall deficit (DEC-017)
Nov 2024–May 2025 season total vs a **1991–2020** (30-season) Nov–May climatological
normal, per AOI, AOI-mean (CHIRPS ~5566 m ≫ field, so not cropland-masked). CHIRPS
ID `UCSB-CHG/CHIRPS/DAILY` (DEC-013). Columns: `aoi_id, name,
season_total_mm_2024_2025, climatology_mm_1991_2020, deficit_mm, deficit_pct`.

| AOI | actual mm | normal mm | deficit |
|---|---|---|---|
| Deir ez-Zor | 108.3 | 146.6 | −26.1% |
| Raqqa | 142.8 | 178.0 | −19.8% |
| Hasakah | 237.7 | 318.4 | −25.3% |
| Latakia | 608.2 | 790.1 | −23.0% |

### `ndvi_anomaly_2025.tif` — NDVI anomaly on cropland (DEC-018)
Sentinel-2 (`S2_SR_HARMONIZED`) growing-season (Mar–May) per-pixel **MAX** NDVI for
2025 minus the **2019–2024** mean (S2-archive-limited normal), SCL cloud-masked,
bilinear 10 m→30 m. float32, nodata −9999, **EPSG:32637 @ 30 m**, masked to cropland
**union** (`aois/cropland_mask.tif` value ∈ {1,2,3}, DEC-015). Negative = drought
stress. Per-AOI mean anomaly: Hasakah −0.277, Raqqa −0.197, Deir ez-Zor −0.142,
Latakia −0.054; **87.6%** of cropland pixels negative. Valid cropland px = 2,388,480
ha = the S3 union total (pixel-aligned to the mask). _Gitignored (`*.tif`);
regenerate with `… build_baseline.py ndvi`._

### `production_baseline.csv` — GIEWS ~1.2 Mt floor disaggregated (DEC-019)
The FAO/GIEWS ~1.2 Mt 2025 national cereal floor split across **all 14** Syrian
governorates by cropland-area share (sums to the floor); the 4 study AOIs are flagged
(`is_study_aoi`) and hold ~45% (≈544 kt). Columns: `gaul_adm1, aoi_id, is_study_aoi,
cropland_ha, cropland_share, cereal_production_2025_t`. **Assumes uniform yield per
cropland hectare** — spatial unevenness lives in the NDVI/rainfall layers, not here.

## Context

2025 was a record drought — cereal harvest near 1.2 Mt (~60%+ below average, worst
in ~60 years); ~16.3M people at food-security risk (`docs/PRODUCT.md` §2). The
~20–26% rainfall deficit and pervasive negative NDVI are the drought signal the 2026
flood/fire "whiplash" is measured against.
