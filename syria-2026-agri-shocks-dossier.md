# Syria 2026 Agricultural Shocks — Data-Source Dossier

> **Created:** 2026-06-12 (Session 2, W-reference)
> **Companion to:** `docs/PRODUCT.md` (intent, RQs), `docs/STRUCTURE.md` (architecture, §5 source contracts, §6 validation, §9 conventions).
> **Purpose:** The full data-source catalog the planning docs reference but had not yet contained — access methods, rate limits, licenses, caveats, and the named validation ground truth. Also records the **live GEE collection-ID verification** (`docs/STRUCTURE.md` §9: *verify every ID against the live catalog before wiring it in*).
> **Scope discipline:** This dossier documents *within* the pinned contracts (`docs/STRUCTURE.md` §3, §10). Where it found a live-catalog discrepancy vs §5 it is **flagged, not silently resolved** (see §2 and DEC-012 in `tracking/DECISIONS.md`).

---

## 1. How sources map to the work

| Phenomenon / layer | Primary sources | Validation ground truth |
|---|---|---|
| **Floods → damaged cropland** (W4 / S6) | Sentinel-1 SAR (load-bearing), Sentinel-2 + Dynamic World (confirmatory), JRC GSW (subtract permanent water), GLO-30 DEM | GloFAS discharge + any Copernicus EMS flood activation for the window |
| **Fires → damaged cropland** (W5 / S7) | FIRMS **VIIRS 375 m** (detection, via API), Sentinel-2 dNBR (scar + severity), Dynamic World (cropland baseline); MODIS MCD64A1 = monthly burned-area **context only** | **Copernicus EMS EMSR811** (Latakia, Jul 2025); PAX Sentinel-2 methodology as precedent |
| **2025 drought baseline** (W2 / S4) | CHIRPS (rainfall deficit), Sentinel-2 (NDVI anomaly), GIEWS (~1.2 Mt floor) | Cross-check vs FAO/GIEWS narrative (~60%+ below average) |
| **RQ1 flood attribution** (W7 / S9) | CHIRPS rainfall vs GloFAS discharge, against reported Euphrates flows | — (reasoning-heavy; proportionate claims) |
| **RQ2 fire attribution** (W8 / S10) | ACLED conflict events × validated VIIRS/dNBR | PAX methodology precedent |
| **RQ3 control overlay** (W9 / S11) | Validated damage × indicative control boundaries | descriptive only (DEC-005) |

---

## 2. GEE collection-ID verification (live catalog, 2026-06-12)

Verified programmatically via `clients.gee_auth.initialize()` (service-account auth, project `rich-stratum-429021-u4`) calling `ee.data.getAsset(<id>)` against the live `earthengine-public` catalog. Result: **8 of 9 IDs in `docs/STRUCTURE.md` §5 resolve exactly as written; 1 is corrected.**

| §5 declared ID | Live status | Asset type | Notes |
|---|---|---|---|
| `COPERNICUS/S1_GRD` | ✅ verified | IMAGE_COLLECTION | Sentinel-1 GRD |
| `COPERNICUS/S2_SR_HARMONIZED` | ✅ verified | IMAGE_COLLECTION | Sentinel-2 MSI L2A (harmonized) |
| `GOOGLE/DYNAMICWORLD/V1` | ✅ verified | IMAGE_COLLECTION | bands incl. `water`, `flooded_vegetation`, `crops`, `label` |
| `JRC/GSW1_4/GlobalSurfaceWater` | ✅ verified | **IMAGE** (not a collection) | coverage 1984-03-16 → 2022-01-01 |
| `UCSB/CHG/CHIRPS/DAILY` | ❌ **NOT FOUND** → corrected to **`UCSB-CHG/CHIRPS/DAILY`** | IMAGE_COLLECTION | see correction note below |
| `COPERNICUS/DEM/GLO30` | ✅ verified | IMAGE_COLLECTION | Copernicus GLO-30 DEM |
| `MODIS/061/MCD64A1` | ✅ verified | IMAGE_COLLECTION | monthly burned area (context only) |
| `ESA/WorldCover/v200` | ✅ verified | IMAGE_COLLECTION | Cropland = class value **40** |
| `FIRMS` | ✅ verified | IMAGE_COLLECTION | **MODIS-derived** on GEE (bands `T21`,`confidence`,`line_number`) — confirms §5: use the **API for VIIRS**, not this collection, for detection |

### CHIRPS correction — flagged drift vs §5

- **§5 says:** `UCSB/CHG/CHIRPS/DAILY` (all slashes). **Live catalog:** that path is **not found**; the working ID is **`UCSB-CHG/CHIRPS/DAILY`** (hyphen between `UCSB` and `CHG` — the provider namespace is `UCSB-CHG`).
- **Confirmed loadable, not just resolvable:** 31 daily images for Jan 2025, single band `precipitation`, native scale ~5566 m (≈0.05°), real value sampled over Deir ez-Zor (~0.31 mm/day mean, Jan 2025).
- **Action (per `docs/STRUCTURE.md` Working Rules / CLAUDE.md):** recorded as **DEC-013** in `tracking/DECISIONS.md` and surfaced to the human; **§5 is not edited silently.** S4 (baseline) and S5 (`chirps.py`) must use `UCSB-CHG/CHIRPS/DAILY`.

### Band / class facts captured for downstream contracts

- **Dynamic World** bands: `water, trees, grass, flooded_vegetation, crops, shrub_and_scrub, built, bare, snow_and_ice, label` → S3 cropland mask uses `crops`; S6 flood-confirm may use `water` / `flooded_vegetation`.
- **ESA WorldCover v200** classes: Cropland = **40** (full map: 10 Tree, 20 Shrub, 30 Grass, 40 Cropland, 50 Built, 60 Bare, 70 Snow/ice, 80 Water, 90 Herbaceous wetland, 95 Mangrove, 100 Moss/lichen) → S3 mask reconciliation key.
- **Sentinel-1 GRD** band caveat: polarization **varies by scene** (the first April-2026 scene sampled was `HH`/`HV`; Syria land scenes are commonly `VV`/`VH`). S6 must **filter by `transmitterReceiverPolarisation`** rather than assume a fixed band pair.
- **MCD64A1** bands: `BurnDate, Uncertainty, QA, FirstDay, LastDay` — monthly burned-area context only (DEC-006); **never** fire detection.

---

## 3. GEE-hosted sources (raster backbone)

All accessed through Earth Engine (`earthengine-api`), auth via `clients/gee_auth.py` (service account preferred — DEC-012; cached user creds fallback — DEC-011). All IDs as verified in §2.

| Source | Role | GEE ID | Native res | Key bands / use | License |
|---|---|---|---|---|---|
| Sentinel-1 SAR (GRD) | Flood (F) | `COPERNICUS/S1_GRD` | 10 m | `VV`/`VH` (or `HH`/`HV`) backscatter; **load-bearing** flood extent through cloud | Copernicus — free & open (attribution) |
| Sentinel-2 SR (L2A) | Flood/Fire (F) | `COPERNICUS/S2_SR_HARMONIZED` | 10–20 m | NDVI (baseline), dNBR (fire scar+severity), optical flood confirm | Copernicus — free & open |
| Dynamic World | Flood/Fire/mask (F) | `GOOGLE/DYNAMICWORLD/V1` | 10 m | `crops` (mask), `water`/`flooded_vegetation` (flood confirm) | CC-BY-4.0 |
| JRC Global Surface Water | Baseline subtract (B) | `JRC/GSW1_4/GlobalSurfaceWater` | 30 m | permanent-water `occurrence` → **subtract** from flood extent | Copernicus/JRC — free |
| CHIRPS daily | Baseline + RQ1 (F/B) | **`UCSB-CHG/CHIRPS/DAILY`** | ~0.05° (~5.5 km) | `precipitation` (mm/day); rainfall deficit + RQ1 signal | Public domain / open (UCSB-CHG) |
| Copernicus GLO-30 DEM | Flood (F) | `COPERNICUS/DEM/GLO30` | 30 m | terrain for flood plausibility / drainage | Copernicus — free |
| MODIS MCD64A1 | Burned-area context (F/B) | `MODIS/061/MCD64A1` | 500 m | monthly burned area — **context only**, never detection | NASA — public domain |
| ESA WorldCover v200 | Mask reconciliation (B) | `ESA/WorldCover/v200` | 10 m | Cropland class **40** → reconcile vs Dynamic World `crops` | CC-BY-4.0 |
| FIRMS (on GEE) | — | `FIRMS` | 1 km | **MODIS-derived** — do **not** use for detection; VIIRS via API (§4) | NASA — public domain |

> **Caveat (GSW versioning):** `JRC/GSW1_4/GlobalSurfaceWater` is the v1.4 monthly-history-derived global layer (1984–2021 inputs). Newer GSW releases exist; v1.4 is pinned here because it resolves live and matches §5. Revisit only via a logged decision.

---

## 4. Non-GEE sources (API / portal)

### 4.1 FIRMS — active-fire detection (VIIRS 375 m) — **DEC-006 primary fire sensor**
- **Access:** REST API with a free `MAP_KEY`. Request one at <https://firms.modaps.eosdis.nasa.gov/api/map_key/>; key from env `MAP_KEY` (never hard-coded — DEC-011 pattern).
- **Endpoint for AOI pulls:** the *area* API, `…/api/area/csv/{MAP_KEY}/{SOURCE}/{bbox}/{day_range}/{date}` (<https://firms.modaps.eosdis.nasa.gov/api/area/>).
- **VIIRS products (use these, not MODIS):** `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` (NRT); `VIIRS_SNPP_SP` for the science-quality archive. 375 m nominal pixel.
- **Rate limit:** **5,000 transactions per 10-minute** window per `MAP_KEY`; multi-day requests count as multiple transactions. Higher limits by request to NASA. → mandates the cached/checkpointed client (§9); retries must **never** re-pull.
- **License:** NASA/LANCE — open, attribution requested.

### 4.2 ACLED — conflict events (RQ2)
- **⚠ Access model changed — flag for S5/S10:** ACLED has moved to **OAuth via a `myACLED` account**; the legacy single "API key" flow is deprecated. You register once (institutional/organizational **domain email** preferred — a generic `gmail.com` may receive a lower access tier), then authenticate API calls with an **OAuth token** (or cookie auth for browser/tool access).
- **Register:** <https://acleddata.com/register/> → see API docs <https://acleddata.com/acled-api-documentation> and access guide <https://acleddata.com/methodology/acled-access-guide>.
- **Env config:** keep `ACLED_KEY` / `ACLED_EMAIL` (README convention) but the S5 client must implement the **OAuth token exchange**, not a static key query string. Tiers/limits are account-determined — confirm headroom at runtime and cache (§9).
- **Export formats:** CSV / JSON.
- **License:** ACLED Terms of Use — attribution required, redistribution restricted (not fully open). Treat as proprietary; cite, don't republish raw.

### 4.3 GloFAS — river discharge (floods + RQ1; validation)
- **Access:** Copernicus Emergency Management / Early Warning **Data Store** via the `cdsapi` Python client.
- **Dataset (historical reanalysis):** **`cems-glofas-historical`** (GloFAS-ERA5, 1979→present; GloFAS consolidated stream ~2–3 months behind real time, GloFAST intermediate ~2–5 days behind). Overview: <https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical>.
- **Note:** the store migrated from the legacy `cds.climate.copernicus.eu` to the **Early Warning Data Store (`ewds.climate.copernicus.eu`)** — point `cdsapi` at the EWDS endpoint/key. Requires a free CDS/ECMWF account + accepting the dataset licence.
- **Use:** Euphrates-reach discharge series for the flood window, compared against reported flows (~2,000 m³/s vs 200–250 in drought years — `docs/PRODUCT.md` §2) to discriminate rainfall vs upstream release. **Proportionate claims only** (§9).
- **License:** Copernicus — free & open (licence acceptance in CDS/EWDS).

### 4.4 HDX / ReliefWeb — corroborating reports (context)
- **HDX:** Humanitarian Data Exchange API (CKAN-based) — <https://data.humdata.org/>. Datasets vary in license per provider (often CC-BY / CC-BY-IGO).
- **ReliefWeb:** public API <https://apidoc.reliefweb.int/> — situation reports / news for narrative corroboration of event windows and impact. Attribution per source.
- **Use:** S5 `hdx.py`; corroboration, not primary measurement. Cache (§9).

### 4.5 GIEWS / FEWS NET / IPC — food-security baseline & join (W2, W6)
- **GIEWS (FAO):** country briefs / production figures — the ~1.2 Mt 2025 cereal floor and ~2.3 Mt 2026 rebound projection (`docs/PRODUCT.md` §2). Web + data download.
- **FEWS NET:** food-security outlooks / IPC-style phase classifications; data portal with downloadable layers.
- **IPC:** Integrated Food Security Phase Classification — phase reference for the W6 phase-delta join (§3.4).
- **Use:** baseline magnitudes (S4) and the food-security translation (S8). Verify latest figures against FAO/GIEWS and FEWS NET **before publication** (PRODUCT §2 caveat). Licenses: generally open with attribution; confirm per artifact.

---

## 5. Validation ground truth (Tier-2 — human-gated, §6 / DEC-007)

These are the **named** references a human compares Tier-2 outputs against. No agent/Workflow run may flip `validation_status` to `validated`.

| Phenomenon | Named ground truth | Detail |
|---|---|---|
| **Fire** | **Copernicus EMS EMSR811** | Wildfire activation, **Latakia region, Syria — activated 3 July 2025**, coastal mountains; rapid-mapping delineation/grading products. Portal: <https://mapping.emergency.copernicus.eu/activations/EMSR811/>. This is the project's documented anchor/precedent. |
| **Fire** | **PAX Sentinel-2 methodology** | Methodological precedent for Sentinel-2 burn-scar mapping in Syria (not a data product) — cite as method, reproduce the approach. |
| **Floods** | **GloFAS discharge** | `cems-glofas-historical` reach discharge over the flood window — compare modeled surge timing/magnitude against detected flood extent. |
| **Floods** | **Copernicus EMS flood activation** (if any for the window) | Check the CEMS activations list (<https://mapping.emergency.copernicus.eu/activations/>) for a Mar–Jun 2026 Euphrates/Deir ez-Zor flood activation; use its delineation if present. *(Existence not yet confirmed — S6 to check live.)* |

---

## 6. Event windows (context — from `docs/PRODUCT.md` §2)

- **Floods (S6/W4):** March–June 2026 — April floods + hailstorms (wheat at critical final growth stage), then the **late-May Euphrates surge** (flows ~2,000 m³/s; dam spillway gates opened first time in 30+ years). AOIs: **Deir ez-Zor, Raqqa, Hasakah**.
- **Fires (S7/W5):** May–July 2026 fire season. AOIs: **Hasakah** (cropland fires), **Latakia** (coastal/forest). **July 2025 Latakia (EMSR811)** is the documented precedent, not the 2026 subject.
- **Baseline (S4/W2):** 2025 record drought — CHIRPS deficit window **Nov 2024 – May 2025**; GIEWS ~1.2 Mt floor.

---

## 7. Conventions & cross-cutting caveats (mirrors `docs/STRUCTURE.md` §9)

- **Verify GEE IDs live before wiring** — done 2026-06-12 (§2); re-verify if a session is months later (IDs are versioned).
- **Cache & checkpoint every external pull** — rate-limit safety (FIRMS 5,000/10 min, ACLED account tiers) + reproducibility; **retry loops must never re-pull**.
- **VIIRS, not MODIS, for fire detection** (DEC-006). MODIS MCD64A1 = monthly burned-area context only.
- **SAR is load-bearing for floods; optical is confirmatory** (DEC-006). Subtract JRC GSW permanent water.
- **Document cropland-mask disagreement** (Dynamic World `crops` vs WorldCover class 40) — S3.
- **Proportionate claims** — dam attribution (RQ1) is politically charged; RQ3 is descriptive only (DEC-005). Attribute sources; never overclaim (PRODUCT §9).
- **Secrets from env / `secrets/` (gitignored)** — `MAP_KEY`, ACLED OAuth creds, GEE service-account key, CDS/EWDS key. Never hard-coded, never committed.

---

## 8. License summary (confirm exact terms at source before publication)

| Source | License (working assumption) | Redistribution |
|---|---|---|
| Sentinel-1/-2, GLO-30 DEM, JRC GSW, GloFAS | Copernicus — free & open | Yes, with attribution |
| CHIRPS | Public domain / open (UCSB-CHG) | Yes |
| Dynamic World, ESA WorldCover | CC-BY-4.0 | Yes, with attribution |
| MODIS MCD64A1, FIRMS | NASA — public domain | Yes |
| ACLED | Proprietary — Terms of Use, attribution | **Restricted** — cite, don't republish raw |
| HDX / ReliefWeb / GIEWS / FEWS NET / IPC | Per-provider (often CC-BY / open) | Confirm per artifact |

> Licenses above are working assumptions for the well-established open sources; **confirm the exact licence text at each source before any publication** (proportionate-claims discipline). ACLED in particular restricts redistribution.
