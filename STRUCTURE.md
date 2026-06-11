# STRUCTURE — Syria 2026 Agricultural Shocks

> **Version:** 0.1 (planning seed)
> **Status:** Planning. Pins settled decisions and contracts; continued planning in Claude Code fills in *within* these boundaries.
> **Companion docs:** `PRODUCT.md` (intent, scope, RQs), `syria-2026-agri-shocks-dossier.md` (full source catalog, access methods, caveats).

## 1. Architecture overview

Two parallel pipelines (floods, fires) in one repository, sharing a common AOI grid, a single damage schema, and one food-security impact layer. Both pipelines emit the **same** output — damaged cropland hectares per AOI per date — which is what makes this one project rather than two.

```
floods ─┐
        ├─> shared damage schema ─> food-security impact layer ─> RQ analyses
fires ──┘                              (vs 2025 drought baseline)
```

## 2. Repository layout

```
syria-agri-shocks-2026/
├── PRODUCT.md
├── STRUCTURE.md
├── aois/                 # canonical AOIs + cropland mask (shared, §3.1)
│   ├── governorates.geojson
│   ├── cropland_mask.tif
│   └── control_areas.geojson      # RQ3 — indicative only, descriptive overlay
├── baseline/             # 2025 drought reference (§3.3)
│   ├── ndvi_anomaly_2025.tif
│   ├── rainfall_deficit.csv
│   └── production_baseline.csv
├── clients/              # external-source API clients (cached, §9)
│   ├── firms.py  chirps.py  acled.py  hdx.py  gee_auth.py
├── pipelines/
│   ├── floods/           # flood_mask.py  cropland_flooded.py  attribution.py
│   └── fires/            # active_fire.py  burn_severity.py  attribution.py
├── schema/               # shared damage schema (§3.2)
├── food_security/        # impact_layer.py (§3.4)
├── analysis/             # whiplash.py  control_differential.py
├── tracking/             # plan-sessions output + progress tracker live here
└── outputs/              # tables, masks, figures
```

## 3. Core contracts (pinned — do not reopen in continued planning)

### 3.1 AOI & cropland mask
Canonical AOIs: Deir ez-Zor, Raqqa, Hasakah (floods); Hasakah, Latakia (fires). One cropland mask, reconciled from Dynamic World and ESA WorldCover, with disagreement documented. Every module consumes these canonical assets; no module redefines AOIs.

### 3.2 Shared damage schema (the integration contract)
Every damage record, from either pipeline, conforms to one schema keyed on:
`aoi_id, date, phenomenon {flood|fire}, severity_class, source_layer, damaged_cropland_ha, validation_status {unvalidated|validated|rejected}`.
The food-security layer and all RQ analyses consume **only** this schema. Nothing downstream reads a pipeline's internal rasters directly.

### 3.3 Baseline contract (2025 drought)
Reference layers, computed once, not per run: NDVI anomaly on cropland (drought stress), CHIRPS rainfall deficit (Nov 2024–May 2025), and the GIEWS ~1.2 Mt production floor disaggregated by governorate. All 2026 damage is expressed relative to this baseline.

### 3.4 Food-security join contract
`damaged_cropland_ha` → estimated production loss → food-security phase delta, joined to GIEWS / FEWS NET / IPC (and WFP / FAO ASIS as available), referenced against §3.3.

## 4. Pipelines

### Pipeline A — Floods (primary driver)
- **Window:** March–June 2026 (April floods/hailstorms + late-May Euphrates surge).
- **AOIs:** Deir ez-Zor, Raqqa, Hasakah.
- **Core data:** Sentinel-1 SAR (load-bearing — extent through cloud), Sentinel-2 + Dynamic World (`water`/`flooded vegetation`/`crops`), JRC Global Surface Water (subtract permanent river), GloFAS + CHIRPS (RQ1 signal), Copernicus GLO-30 DEM.
- **Outputs:** flood masks → `damaged_cropland_ha`; flow-vs-rainfall series for RQ1.

### Pipeline B — Crop fires
- **Window:** May–July 2026 fire season; July 2025 Latakia (EMSR811) as documented anchor.
- **AOIs:** Hasakah (cropland fires), Latakia (coastal/forest).
- **Core data:** FIRMS VIIRS (375 m, **not** MODIS 1 km), Sentinel-2 dNBR (scar + severity), MODIS MCD64A1 (burned area), Dynamic World (cropland baseline).
- **Outputs:** burned-cropland hectares + severity → `damaged_cropland_ha`; ACLED-overlaid hotspots for RQ2.

## 5. Data source contracts (operative subset)

Role: **F** = 2026 focus · **B** = baseline only · **V** = validation. Full catalog, licenses, and caveats in the companion dossier. **Verify all GEE IDs against the live catalog before use.**

| Source | Role | Access | GEE ID (verify) |
|---|---|---|---|
| FIRMS (VIIRS) | F | API + free `MAP_KEY` | `FIRMS` (MODIS only on GEE; VIIRS via API) |
| Sentinel-1 SAR | F | GEE | `COPERNICUS/S1_GRD` |
| Sentinel-2 | F | GEE | `COPERNICUS/S2_SR_HARMONIZED` |
| Dynamic World | F | GEE | `GOOGLE/DYNAMICWORLD/V1` |
| JRC Global Surface Water | B | GEE | `JRC/GSW1_4/GlobalSurfaceWater` |
| CHIRPS daily | F/B | GEE | `UCSB/CHG/CHIRPS/DAILY` |
| GLO-30 DEM | F | GEE | `COPERNICUS/DEM/GLO30` |
| MODIS Burned Area | F/B | GEE | `MODIS/061/MCD64A1` |
| ESA WorldCover | B | GEE | `ESA/WorldCover/v200` |
| GloFAS | F/V | CDS API + portal | n/a |
| ACLED | F | API + key | n/a |
| GIEWS / FEWS NET / IPC | F | web + data | n/a |
| HDX / ReliefWeb | F | API | n/a |
| Copernicus EMS (EMSR811) | V | portal download | n/a |

## 6. Validation & definition of done (first-class)

Two tiers. The continued planning must instantiate the second tier as per-session `Completion criteria` when `plan-sessions` runs.

**Tier 1 — agent-verifiable.** Code correctness, schema conformance, unit tests, API plumbing, caching, reproducibility. Claude Code may mark these done on its own evidence.

**Tier 2 — human-gated (visual / empirical).** Flood masks, burn scars, and any `damaged_cropland_ha` derived from them. These are **not done** until a human has compared the output against named ground truth:
- Floods → GloFAS, plus any Copernicus EMS flood activation for the window.
- Fires → Copernicus EMS EMSR811; PAX Sentinel-2 methodology as precedent.

**Hard rule.** Tests passing, or agent convergence, is **not** correctness for Tier-2 outputs. The food-security layer and RQ analyses must refuse to consume any record whose `validation_status != validated`. No Workflow/parallel run may set a Tier-2 output to `validated`; only a human does.

## 7. Work breakdown & sessionization hints (feeds plan-sessions)

Units with dependencies, complexity, and parallel-eligibility, so Step 2 of `plan-sessions` has real material. "Parallel-eligible" = meets the skill's rubric (≥2 non-trivial tasks, disjoint files, no shared schema). All Tier-2 validation stays sequential and human regardless.

| Unit | Work | Depends on | Notes |
|---|---|---|---|
| W0 | Repo scaffold, env (WSL2/conda), GEE auth, shared schema | — | Foundation; sequential |
| W1 | AOIs + reconciled cropland mask | W0 | Sequential |
| W2 | 2025 baseline layers | W1 | Read/compute heavy; keep in its own session |
| W3 | API clients: FIRMS, CHIRPS, ACLED, HDX/ReliefWeb | W0 | **Parallel-eligible** (disjoint files) — Workflow candidate |
| W4 | Pipeline A flood masks → damage | W1 | **Tier-2 human-gated**; mask generation per sub-AOI may fan out, validation does not |
| W5 | Pipeline B fire layers → damage | W1 | **Tier-2 human-gated**; same rule |
| W6 | Food-security join / impact layer | W2,W4,W5 | Consumes validated records only |
| W7 | RQ1 flood attribution | W4 + CHIRPS/GloFAS | Reasoning-heavy |
| W8 | RQ2 fire attribution | W5 + ACLED | Reasoning-heavy |
| W9 | RQ3 descriptive control overlay | W4/W5 + indicative boundaries | Descriptive only — no causal or differential claim |
| W10 | Verification / reproducibility pass | after W6 | A `plan-sessions` verification session |

## 8. Tech stack & environment

- **Python:** geopandas, rasterio, xarray, `earthengine-api`, pandas.
- **GEE** as the raster backbone; local Python for vector joins and tabular impact tables.
- **Windows:** use WSL2 or conda for GDAL/rasterio; do not rely on native pip wheels.
- **Auth (interactive, human-run once):** `earthengine authenticate`; FIRMS `MAP_KEY`; Copernicus Data Space account; ACLED key.

## 9. Conventions

- Verify every GEE collection ID against the live catalog before wiring it in (IDs are versioned).
- All external pulls are cached and checkpointed — required for rate-limit safety (FIRMS 5,000/10 min, ACLED tiers) and reproducibility, and so retry loops never re-pull.
- VIIRS, not MODIS, for fire detection; MODIS only for monthly burned-area context.
- SAR is load-bearing for floods; treat optical as confirmatory.
- Document cropland-mask disagreement (Dynamic World vs WorldCover).
- Every Tier-2 artifact carries a `validation_status`; default `unvalidated`.

## 10. Locked decisions (seed for the Decision & Change Log — do not reopen)

1. Scope is 2026 events; all pre-2026 data is baseline/context only.
2. Two phenomena, two parallel pipelines, one repo, one shared damage schema.
3. No deep-learning/CV pipeline; no earthquake analysis.
4. Primary question is food-security impact vs the 2025 drought baseline.
5. Secondary questions: flood attribution, fire attribution, and a descriptive damage-vs-control overlay (RQ3 is descriptive only, never a differential or causal claim).
6. Sentinel-1 SAR is the primary flood sensor; FIRMS VIIRS the primary fire-detection sensor.
7. Human-in-the-loop validation is mandatory for all Tier-2 outputs; agents cannot self-certify them.
