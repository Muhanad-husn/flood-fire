# Syria 2026 Agricultural Shocks — Multi-Session Implementation Plan

> **Created:** 2026-06-12
> **Source plan:** `docs/STRUCTURE.md` §7 (work breakdown W0–W10), governed by `docs/PRODUCT.md` (intent, RQs) and `docs/STRUCTURE.md` §3/§5/§6/§10 (contracts, data sources, validation, locked decisions).
> **Total sessions:** 12
> **Estimated total effort:** ~12 sessions (3 foundation/reference, 2 shared assets, 1 parallel clients, 2 Tier-2 pipelines, 1 impact join, 3 RQ analyses, 1 verification).

## Overview

This plan turns the pinned contracts and the W0–W10 work breakdown into twelve dependency-ordered, resumable Claude Code sessions. Each session produces one self-contained deliverable; the two pipeline sessions (floods, fires) and every `damaged_cropland_ha` output are **Tier-2 human-gated** — their completion criteria below carry explicit human-validation checkboxes that no agent or Workflow run may tick (`docs/STRUCTURE.md` §6, DEC-007).

This document is the **session governance layer**. It does **not** reopen the contracts in `docs/STRUCTURE.md` §3 or the locked decisions in §10 — it fills in *within* them. The canonical decision log remains `tracking/DECISIONS.md` (seeded DEC-001…007); record new decisions there, not in this file.

### Naming / git note

`docs/STRUCTURE.md` §2 names the project `syria-agri-shocks-2026/`; the local checkout is `D:\flood_fire`. This is a cosmetic checkout-dir mismatch only, not a contract drift. The environment reports the working dir is **not** a git repository (a `.git` directory is present but uninitialized for our purposes) — the executor should `git init` (or confirm the branch workflow) before relying on the per-session `Branch` field; if the repo stays non-git, treat `Branch` as advisory and work on the working tree directly.

---

## Session Dependency Graph

```
S1  W0  Foundation (env, GEE auth, schema finalize)        [Tier-1]
 │
 ├─> S2  Data-source dossier + GEE ID verification         [reference]
 │        │
 ├─> S3  W1  AOIs + reconciled cropland mask               [human-reviewed mask]
 │        │        │
 │        │        ├─> S4  W2  2025 baseline layers         [compute-heavy]
 │        │        │            │
 │        │        ├─> S6  W4  Floods → damage             [TIER-2 human-gated]
 │        │        │            │
 │        │        └─> S7  W5  Fires  → damage             [TIER-2 human-gated]
 │        │                     │
 └─> S5  W3  API clients (FIRMS/CHIRPS/ACLED/HDX)  [parallel-eligible]
          │   (informs S6, S7, S9, S10)
          │
          ▼
S4 + (S6 validated) + (S7 validated) ─> S8  W6  Food-security impact   [validated-only gate]
S6 (validated) + CHIRPS/GloFAS       ─> S9  W7  RQ1 flood attribution
S7 (validated) + ACLED               ─> S10 W8  RQ2 fire attribution
S6/S7 (validated) + control_areas    ─> S11 W9  RQ3 descriptive overlay  [descriptive-only]
S8 + S9 + S10 + S11                  ─> S12 W10 Verification / reproducibility pass
```

**Independence notes.** S2 and S3 both depend only on S1 and can run in either order (S2 should precede S6/S7 because it verifies the GEE IDs those sessions wire in). S5 (clients) depends only on S1 and can run any time after it. S6 (floods) and S7 (fires) are mutually independent. S9, S10, S11 are mutually independent and all depend only on their upstream pipeline being **validated**.

---

## Session 1: W0 — Foundation (environment, GEE auth, schema finalization)

**Objective:** Make the repo runnable from a clean checkout and finalize the shared schema so every downstream module has a stable integration contract.
**Inputs:** `docs/STRUCTURE.md` §7 (W0), §8 (tech stack), §9 (conventions); `schema/damage_schema.py`; `clients/gee_auth.py`.
**Outputs:** `environment.yml` (pins the `f_f` conda env, python=3.13, geo stack); wired `clients/gee_auth.py`; finalized `schema/damage_schema.py` (severity vocab + (de)serialization); a short `README`/run note for first-time auth.
**Depends on:** None.
**Branch:** `session/syria-agri-shocks-s1`
**Parallel-eligible task groups:** None (sequential — env, auth, and schema are interdependent and small).

### Context for resumption

The repo is scaffolded: every module is a stub whose docstring already cites the governing contract section, and `schema/damage_schema.py` defines `DamageRecord`, `Phenomenon`, `ValidationStatus`, and the `is_consumable()` downstream gate. The `f_f` conda env (python=3.13) exists but **no dependency manifest is committed**. This session does the mechanical foundation only — read `docs/STRUCTURE.md` §8/§9 and `schema/damage_schema.py` first. Auth is interactive and human-run once (`earthengine authenticate`); wire the code path but expect the human to run the actual auth.

### Steps

1. Write `environment.yml` pinning geopandas, rasterio, xarray, `earthengine-api`, pandas, and GDAL via conda-forge (not pip wheels — §8). Pin to what the live `f_f` env resolves; verify it imports cleanly.
2. Wire `clients/gee_auth.py`: an idempotent `initialize()` that uses cached credentials, raises a clear instruction to run `earthengine authenticate` if absent, and never re-auths in a retry loop (§9).
3. Finalize `schema/damage_schema.py` per the `TODO(W0)`: define the `severity_class` vocabulary **per phenomenon** (flood severity bins vs fire dNBR severity bins) and add (de)serialization to the canonical `outputs/` table format (CSV/Parquet round-trip).
4. Record the auth/env bootstrap steps in a short run note (where a fresh user starts).
5. Log any new decision (e.g., chosen severity vocab, table format) in `tracking/DECISIONS.md`.

### Completion criteria

- [x] `conda env create -f environment.yml` (or update) resolves and the geo stack imports without error.
- [x] `gee_auth.initialize()` succeeds against cached creds and gives an actionable message when creds are missing.
- [x] `DamageRecord` round-trips through (de)serialization; `severity_class` vocab is documented per phenomenon.
- [x] Severity vocab + table-format choices recorded in `tracking/DECISIONS.md`.

### Handoff notes

**Status: Complete (2026-06-12).** Repo is runnable from a clean checkout; schema is finalized as the stable integration contract. Tier-1 only — no Tier-2 gates in this session.

**What was built / changed:**
- `environment.yml` already existed and was correct (geo stack + DEC-008 viz deps + pytest). The `f_f` conda env was **bare (22 base pkgs)**, so I ran `conda env update -n f_f -f environment.yml`. It now imports cleanly: geopandas 1.1.3, rasterio 1.5.0, xarray 2026.4.0, pandas 2.3.3, pyarrow, ee, seaborn/matplotlib/contextily/folium/geemap.
- `schema/damage_schema.py` — finalized the `TODO(W0)`: `SEVERITY_CLASSES` per phenomenon, `validate_record()` (vocab + non-damage-class-is-0ha + non-negative gates), `__post_init__` enum coercion, and lossless CSV (stdlib) + Parquet (pandas) (de)serialization. **The schema core imports no geo/pandas deps** — pandas is a lazy import only inside the Parquet helpers, so the contract stays runnable anywhere.
- `schema/test_damage_schema.py` — 7 Tier-1 tests (kept inside the established `schema/` package, not a new top-level dir). `conda run -n f_f python -m pytest schema/` → **7 passed**. Parquet test `importorskip`s pandas/pyarrow so it's safe without the geo env.
- `clients/gee_auth.py` — idempotent `initialize(project=None, force=False)`, `EE_PROJECT` from env, module-level latch (no re-auth in retry loops), `GEEAuthError` with the `earthengine authenticate` remedy. Verified: imports clean; on this (un-authed) machine `initialize()` raises the actionable hint as designed. **The success-on-cached-creds branch is human-gated** — a human must run `earthengine authenticate` + set `EE_PROJECT` once before any GEE session (S3+) actually pulls.
- `README.md` (new, repo root) — first-run bootstrap: env → `earthengine authenticate`/`EE_PROJECT` → API keys (`MAP_KEY`, `ACLED_KEY`/`ACLED_EMAIL`). Plan-sanctioned S1 output.
- `tracking/DECISIONS.md` — logged **DEC-009** (severity vocab per phenomenon), **DEC-010** (CSV+Parquet canonical table format + round-trip helpers), **DEC-011** (GEE auth via `EE_PROJECT`, idempotent, no interactive flow in code).

**For the next session (S2 — dossier + GEE ID verification):**
- S2 depends only on S1 and needs a **working `gee_auth`** to query the live catalog — but **GEE is not yet authenticated on this machine.** Before S2 can verify IDs against the live catalog, the human must run `earthengine authenticate` and `export EE_PROJECT=<project>`. Flag this at S2 start; it's the one human prerequisite.
- S2 verifies the §5 GEE IDs and writes the missing `syria-2026-agri-shocks-dossier.md`. Do **not** invent IDs/caveats — verify each live and cite. S3 (AOIs/mask) should consume S2's verified DW/WorldCover IDs.
- Severity vocab strings are now pinned (DEC-009): W4 floods must emit `transient|persistent|permanent_excluded`; W5 fires must emit `unburned|low|moderate_low|moderate_high|high`. Pipelines write `DamageRecord`s via `schema.damage_schema.write_csv`/`write_parquet`, never ad-hoc.
- Benign noise to ignore: `conda run` prints a `gdk-pixbuf libpixbufloader_svg.dll` warning on every invocation (librsvg loader registration on Windows) — unrelated to our stack; filter it. Also, `conda run -n f_f python -c "<multiline>"` fails with "arguments contain newlines not implemented" — write the script to a temp file and run that instead.

---

## Session 2: Data-source dossier + GEE collection-ID verification

**Objective:** Produce the missing companion dossier (`syria-2026-agri-shocks-dossier.md`) and verify every GEE collection ID against the live catalog, de-risking all later data-pull sessions.
**Inputs:** `docs/STRUCTURE.md` §5 (data-source contracts table + GEE IDs to verify), §9 (conventions); `docs/PRODUCT.md` §5/§6 (named ground truth); a working `gee_auth` (S1).
**Outputs:** `syria-2026-agri-shocks-dossier.md` at repo root (full source catalog: access methods, rate limits, licenses, caveats, named validation ground truth EMSR811/GloFAS); a verification note recording the confirmed (or corrected) GEE IDs.
**Depends on:** S1.
**Branch:** `session/syria-agri-shocks-s2`
**Parallel-eligible task groups:** None (one document + one verification pass; small and cross-referential).

### Context for resumption

The dossier is referenced throughout `CLAUDE.md`, `PRODUCT.md`, and `STRUCTURE.md` but **does not yet exist**. `STRUCTURE.md` §5 already holds the *operative subset* (the table); this session expands it into the full catalog and, critically, verifies the IDs marked "(verify)" against the **live GEE catalog** — IDs are versioned and must never be wired in unverified (§9). Do NOT invent IDs or caveats from memory; verify each against the live catalog and cite the source. This is a reference/research session: front-loaded reading, one document out.

### Steps

1. For each row in `docs/STRUCTURE.md` §5, confirm the GEE ID resolves in the live catalog (`COPERNICUS/S1_GRD`, `COPERNICUS/S2_SR_HARMONIZED`, `GOOGLE/DYNAMICWORLD/V1`, `JRC/GSW1_4/GlobalSurfaceWater`, `UCSB/CHG/CHIRPS/DAILY`, `COPERNICUS/DEM/GLO30`, `MODIS/061/MCD64A1`, `ESA/WorldCover/v200`). Record exact verified IDs; note any that moved/versioned.
2. Document the non-GEE access paths and limits: FIRMS `MAP_KEY` (VIIRS 375 m, 5,000 req/10 min), ACLED key/tiers, GloFAS via CDS API/portal, HDX/ReliefWeb API, GIEWS/FEWS NET/IPC.
3. Capture validation ground truth explicitly: Copernicus EMS **EMSR811** (fire), GloFAS + any EMSR flood activation for the window (floods), PAX Sentinel-2 methodology as fire precedent.
4. Note licenses/caveats and the SAR-load-bearing / VIIRS-not-MODIS conventions (§9, DEC-006).
5. Record any ID correction as a decision in `tracking/DECISIONS.md` and, if it contradicts §5, **flag the drift** for the human rather than silently editing §5.

### Completion criteria

- [x] `syria-2026-agri-shocks-dossier.md` exists with every source's access method, limits, license, and caveats.
- [x] Every GEE ID in §5 is marked verified-against-live-catalog (with date) or flagged corrected.
- [x] Named validation ground truth (EMSR811, GloFAS, PAX precedent) documented for both phenomena.
- [x] Any ID/source discrepancy vs §5 surfaced to the human (not silently resolved).

### Handoff notes

**Status: Complete (2026-06-12).** Reference session — the companion dossier now exists and every §5 GEE ID is verified against the live catalog. GEE is authenticated on this machine for the first time (service account), which also unblocks S3/S4/S6/S7.

**What was built / changed:**
- **`syria-2026-agri-shocks-dossier.md`** (repo root, new) — full source catalog: §2 live GEE-ID verification table, §3 GEE sources (res/bands/license), §4 non-GEE (FIRMS/ACLED/GloFAS/HDX/GIEWS), §5 named ground truth, §6 event windows, §7 conventions, §8 license summary.
- **GEE is now live.** A **service-account key** (`secrets/rich-stratum-429021-u4-a0736597d906.json`, project `rich-stratum-429021-u4`, SA `cip-346@…`) authenticates headlessly. The earlier `earthengine authenticate` (user OAuth) flow was **blocked by Google deprecating the `drive` scope on the default EE client** — that path is abandoned in favor of the service account.
- **`clients/gee_auth.py`** extended (**DEC-012**): tries a service-account key first (`EE_SERVICE_ACCOUNT_KEY` env, else a lone `service_account` JSON in `secrets/`), falls back to cached user creds; project defaults to the key's `project_id`. Verified end-to-end via `initialize()` (read real S1/CHIRPS/WorldCover data).
- **`.gitignore`** — now ignores the **entire `secrets/` dir** (the SA filename matched none of the prior patterns; a private key was committable). Security fix.
- **`tracking/DECISIONS.md`** — **DEC-012** (service-account auth), **DEC-013** (CHIRPS ID correction + §5 drift flag).

**ID verification result (live, 2026-06-12):** 8/9 §5 IDs verified exactly. **CHIRPS corrected:** `UCSB/CHG/CHIRPS/DAILY` → **`UCSB-CHG/CHIRPS/DAILY`** (hyphen namespace; the slash form is not found). Captured facts: DW `crops` band, WorldCover Cropland = class **40**, JRC GSW is an **Image** not a collection, GEE `FIRMS` is **MODIS-derived** (VIIRS stays on API), S1 polarization **varies by scene** (filter by `transmitterReceiverPolarisation`).

**Two items needing human attention (drift surfaced, not resolved):**
1. **CHIRPS §5 edit** — recommend updating `docs/STRUCTURE.md` §5 to `UCSB-CHG/CHIRPS/DAILY` (or annotate). Left to the human per Working Rules.
2. **ACLED access model changed** — ACLED moved to **OAuth/`myACLED`** (legacy static API key deprecated) and prefers an **institutional-domain email** (a `gmail.com` may get a lower tier). S5 `acled.py` must implement the OAuth token exchange, not a key query string; consider registering with an institutional email if higher-tier access is needed for S10/RQ2.

**For the next session (S3 — AOIs + reconciled cropland mask):**
- GEE is ready; just call `clients.gee_auth.initialize()`. Use the **verified** IDs: `GOOGLE/DYNAMICWORLD/V1` (`crops` band) and `ESA/WorldCover/v200` (Cropland = **40**) for the mask reconciliation (§3.1). Document DW-vs-WorldCover disagreement (§9).
- AOIs: Deir ez-Zor, Raqqa, Hasakah (floods) + Hasakah, Latakia (fires) — five governorates total.
- The cropland mask is **human-reviewed** (S3 Tier gate) before any pipeline consumes it.
- Benign noise to ignore (carried from S1): `conda run` prints a `gdk-pixbuf` librsvg warning on Windows; filter it. `conda run -n f_f python -c "<multiline>"` fails on newlines — write a temp script and run that (temp scripts in `secrets/` are gitignored and easy to clean).

---

## Session 3: W1 — Canonical AOIs + reconciled cropland mask

**Objective:** Build the shared spatial assets every module consumes — governorate AOIs, the reconciled cropland mask (with documented disagreement), and the indicative control-area overlay.
**Inputs:** `docs/STRUCTURE.md` §3.1 (AOI & cropland-mask contract), §4 (per-pipeline AOIs), §9; verified GEE IDs (S2); `aois/README.md`.
**Outputs:** `aois/governorates.geojson` (Deir ez-Zor, Raqqa, Hasakah, Latakia), `aois/cropland_mask.tif` (Dynamic World ∧/∨ ESA WorldCover, reconciled), `aois/control_areas.geojson` (indicative, descriptive overlay), plus a written mask-disagreement note.
**Depends on:** S1 (env/auth); S2 recommended (verified IDs for DW/WorldCover).
**Branch:** `session/syria-agri-shocks-s3`
**Parallel-eligible task groups:** None (single shared asset family; the mask reconciliation is the load-bearing step and must be coherent).

### Context for resumption

`docs/STRUCTURE.md` §3.1 is pinned: **one** cropland mask reconciled from Dynamic World and ESA WorldCover, with disagreement documented; **no module redefines AOIs** — they all consume `aois/`. Canonical AOIs: Deir ez-Zor, Raqqa, Hasakah for floods; Hasakah, Latakia for fires (§4). `control_areas.geojson` is RQ3 material: indicative and descriptive only (DEC-005), boundaries contested. Read §3.1 and §4 before building, and use the GEE IDs verified in S2.

### Steps

1. Assemble `governorates.geojson` for the five AOI governorates from an authoritative admin boundary source; document the source.
2. Build the cropland mask from Dynamic World `crops` and ESA WorldCover cropland; reconcile per §3.1 and **document where the two disagree** (agreement raster + disagreement note).
3. Produce `control_areas.geojson` as an indicative overlay with explicit "contested / descriptive only" provenance in its properties/README.
4. Sanity-check coverage against the pipeline AOIs and the event windows.
5. Record reconciliation rule (e.g., intersection vs union, resolution, CRS) in `tracking/DECISIONS.md`.

### Completion criteria

- [x] `governorates.geojson`, `cropland_mask.tif`, `control_areas.geojson` exist, sourced and documented. *(Vectors EPSG:4326 / GeoJSON standard; raster EPSG:32637 UTM 37N @ 30 m for metric area — each internally consistent, both documented in `aois/README.md`.)*
- [x] Cropland-mask Dynamic World vs WorldCover disagreement is documented (§3.1, §9) — `aois/MASK_DISAGREEMENT.md` (+ in-band classes 1/2/3 and `outputs/aoi_qc/`).
- [x] `control_areas.geojson` carries explicit indicative/descriptive/contested provenance (per-feature `caveat` + `indicative:true`, DEC-005).
- [x] **Human review** of the cropland mask against known agricultural extent — **PASSED (human verdict, 2026-06-12):** reviewed `outputs/aoi_qc/*.png`; the agreement (class 3) extent is accurate against known Syrian agriculture and the DW `crops>0.35` threshold (DEC-015) is confirmed. Mask approved for downstream consumption (Tier-2 gate closed by human, DEC-007).
- [x] Reconciliation rule recorded in `tracking/DECISIONS.md` (DEC-014/015/016).

### Handoff notes

**Status: COMPLETE (2026-06-12).** All three shared spatial assets are built,
verified, documented, and the **human cropland-mask review gate is PASSED** —
reviewed against known Syrian agricultural extent; the agreement-class extent is
accurate and the DW `crops>0.35` threshold (DEC-015) is confirmed (Tier-2 gate
closed by human, §6/DEC-007). The mask is approved for downstream consumption by
S4 (baseline), S6/S7 (pipelines).

**What was built / changed:**
- **`aois/governorates.geojson`** (EPSG:4326) — 4 AOIs from **FAO GAUL 2015 L1**
  (DEC-014): deir_ez_zor (27,307 km²), raqqa (17,906), hasakah (22,758), latakia
  (2,429). Properties: `aoi_id, name, gaul_adm1, area_km2, pipelines`. `aoi_id` is
  the stable key the schema's `aoi_id` field references.
- **`aois/cropland_mask.tif`** (EPSG:32637 / UTM 37N, 30 m, nodata=255) — **one
  categorical reconciliation raster** (DEC-015): `0`=neither, `1`=WorldCover-only,
  `2`=DynamicWorld-only, `3`=both, `255`=outside AOI. **Cropland = {1,2,3} (union);
  3 = intersection.** Sources: WorldCover v200 cls40; DW annual-mean `crops`>0.35
  (2021). Totals: **union 2,388,480 ha; intersection 1,140,395 ha.**
- **`aois/control_areas.geojson`** (EPSG:4326) — **RQ3 INDICATIVE only** (DEC-005).
  5 features; Deir ez-Zor split NE/SW by a *schematic* Euphrates proxy line (former
  AANES / government), others single-labelled from 2017–2024 control geography.
  Every feature carries `caveat` + `indicative:true`. **Not an authoritative map.**
- **`aois/MASK_DISAGREEMENT.md`** — the §3.1/§9 disagreement note (numbers below).
- **`aois/build_aois.py`, `build_control_areas.py`, `qc_preview.py`** — reproducible
  generators (run in that order). **`outputs/aoi_qc/`** — per-AOI PNG previews +
  `summary.json` (the human-review surface).
- **`environment.yml`** — added **geedim** (DEC-016). **`tracking/DECISIONS.md`** —
  DEC-014/015/016.

**The headline finding — cropland-mask disagreement is large and systematic:**
WorldCover is far more liberal than Dynamic World (WC-only 1.21 M ha vs DW-only
0.04 M ha, ~28:1). Per-AOI disagreement (1 − inter/union): **Deir ez-Zor 72%,
Raqqa 64%, Hasakah 44%, Latakia 72%.** Agreement concentrates in irrigated/high-
rainfall cores (N. Jazira, Khabur, Euphrates corridor); WorldCover-only rings them
(rainfed/fallow). **Consequence for W4/W5/W6: report `damaged_cropland_ha` under
BOTH union and intersection as a sensitivity range — union ≈ 2× intersection
overall (≈3.5× in Deir ez-Zor).** The `crops>0.35` DW threshold is the main lever
(DEC-015) — revisit there, not in code, if review finds the extent mis-called.

**For the next session (S4 — 2025 baseline layers):**
- GEE is live; call `clients.gee_auth.initialize()`. Load AOIs from
  `aois/governorates.geojson`; mask NDVI anomaly / deficits to
  `aois/cropland_mask.tif` (**cropland = value ∈ {1,2,3}**, nodata 255). Use the
  S2-verified **`UCSB-CHG/CHIRPS/DAILY`** (DEC-013) for the rainfall deficit.
- **Reuse the geedim tiled-export path (DEC-016)** for the NDVI-anomaly raster —
  `Export…toDrive` is unavailable (Drive scope blocked, DEC-012). Pattern: build
  the image, `prepareForExport(crs="EPSG:32637", scale=…, region=geom)`, then
  `.gd.toGeoTIFF(..., max_tile_dim=1500)`; clip to AOI **locally** after download
  (geedim fills out-of-polygon with 0, NOT nodata — the lesson from S3).
- Decide baseline raster resolution vs the 30 m mask; if you go finer than 30 m,
  resample the mask, don't redefine cropland.

**Gotchas carried forward:**
- `conda run -n f_f python -c "<multiline>"` still fails ("arguments contain
  newlines") — write a temp script (e.g. in gitignored `secrets/`) and run that.
- Filter the benign `gdk-pixbuf`/librsvg warning on every `conda run`.
- geedim per-tile compute can hit "User memory limit exceeded" — keep
  `max_tile_dim≈1500`; the export retry loop in `build_aois.py:export_aoi_mask`
  is the template.
- stdout from a backgrounded `conda run` buffers until exit; tqdm writes `\r`
  progress to stderr. For live progress, tee to a logfile and `tr '\r' '\n'`.
- `aois/_mask_tiles/` is a gitignored GEE-download cache; `mosaic_from_tiles()`
  rebuilds `cropland_mask.tif` from it without re-pulling GEE.

---

## Session 4: W2 — 2025 drought baseline layers

**Objective:** Compute the once-only 2025 drought reference layers that all 2026 damage is expressed against.
**Inputs:** `docs/STRUCTURE.md` §3.3 (baseline contract), §5; `aois/` (S3); CHIRPS via verified ID (S2); `baseline/README.md`; `docs/PRODUCT.md` §2 (the ~1.2 Mt floor, ~60%+ below average).
**Outputs:** `baseline/ndvi_anomaly_2025.tif` (NDVI anomaly on cropland), `baseline/rainfall_deficit.csv` (CHIRPS deficit Nov 2024–May 2025), `baseline/production_baseline.csv` (GIEWS ~1.2 Mt floor disaggregated by governorate).
**Depends on:** S3 (AOIs + cropland mask).
**Branch:** `session/syria-agri-shocks-s4`
**Parallel-eligible task groups:** None (three layers but they share the AOI/cropland mask and one CRS pipeline; compute-heavy — keep coherent in one session).

### Context for resumption

§3.3 is pinned: baseline layers are computed **once, not per run**. Three artifacts: NDVI anomaly on cropland (drought stress), CHIRPS rainfall deficit for the Nov 2024–May 2025 window, and the GIEWS ~1.2 Mt production floor disaggregated by governorate. This is a read/compute-heavy session kept on its own (§7). All three are masked to `aois/cropland_mask.tif` from S3. This is baseline/context only — pre-2026 data is never the subject of analysis (DEC-001).

### Steps

1. Compute the 2025 NDVI anomaly over cropland (Sentinel-2 / appropriate NDVI source vs a multi-year normal), masked to the cropland mask; write `ndvi_anomaly_2025.tif`.
2. Compute CHIRPS rainfall deficit for Nov 2024–May 2025 per AOI; write `rainfall_deficit.csv`.
3. Disaggregate the GIEWS ~1.2 Mt cereal floor by governorate (document the disaggregation key/assumption); write `production_baseline.csv`.
4. Cross-check magnitudes against the PRODUCT.md narrative (~60%+ below average, worst in ~60 years) for plausibility.
5. Record disaggregation assumptions and the NDVI normal period in `tracking/DECISIONS.md`.

### Completion criteria

- [x] All three baseline artifacts exist, masked/keyed to the canonical AOIs.
- [x] Rainfall deficit covers exactly Nov 2024–May 2025; NDVI normal period documented (2019–2024, DEC-018).
- [x] Production floor disaggregation method documented and sums to the GIEWS national floor (1,200,000 t exact).
- [x] Baseline magnitudes are consistent with `docs/PRODUCT.md` §2; assumptions logged in `tracking/DECISIONS.md` (DEC-017/018/019).

### Handoff notes

**Status: COMPLETE (2026-06-12).** All three 2025-drought baseline layers built,
verified, and cross-checked. Tier-1 (compute/reproducibility) — no Tier-2 human
gate in this session. The layers are mutually coherent and consistent with the
record-drought narrative (PRODUCT §2). The mask-aligned NDVI raster confirms the
S3 cropland mask is the load-bearing shared asset working as intended.

**What was built / changed:**
- **`baseline/build_baseline.py`** (new) — one reproducible generator, three
  callable parts (`rainfall` / `production` / `ndvi` / `all`). Reuses the
  `aois/build_aois.py` geedim tiled-export template (DEC-016) for the NDVI raster
  and the DEC-015 cropland definition (DW `crops`>0.35 ∪ WorldCover cls40).
- **`baseline/rainfall_deficit.csv`** (DEC-017) — CHIRPS Nov 2024–May 2025 vs a
  1991–2020 (30-season) normal, AOI-mean. Deficits: Deir ez-Zor −26.1%, Raqqa
  −19.8%, Hasakah −25.3%, Latakia −23.0%.
- **`baseline/ndvi_anomaly_2025.tif`** (DEC-018) — S2 Mar–May peak NDVI, 2025 −
  mean(2019–2024), 30 m EPSG:32637, cropland-union masked. Mean anomaly Hasakah
  −0.277 → Latakia −0.054; 87.6% of cropland negative. **Gitignored (`*.tif`)** —
  regenerate via `… build_baseline.py ndvi` (~9 min/AOI tiled pull). The
  `_ndvi_tiles/` cache (gitignored) lets a re-mosaic skip the GEE pull.
- **`baseline/production_baseline.csv`** (DEC-019) — 1.2 Mt floor disaggregated
  across all 14 governorates by cropland-area share; sums to 1,200,000 t; 4 study
  AOIs = 45% (≈544 kt). Uniform-yield assumption documented.
- **`baseline/README.md`** updated with methods + result tables. **`tracking/
  DECISIONS.md`** — DEC-017/018/019.

**Consistency checks that passed (the headline confidence signal):**
- NDVI valid cropland px = 26,538,663 = **2,388,480 ha = the exact S3 union total**
  → the NDVI export grid is pixel-aligned to `aois/cropland_mask.tif`.
- Production `cropland_ha` (300 m fraction method) matches the 30 m
  `_mask_stats.json` union within ~2% for every study AOI.
- Drought gradient is internally coherent: rainfall deficit, NDVI anomaly, and the
  known cereal geography all agree (inland rainfed Hasakah hardest hit; coastal
  Latakia least).

**For the next session (S5 — W3 API clients; OR S6/S7 pipelines):**
- S5 depends only on S1 and can run now (parallel-eligible: firms/chirps/acled/hdx
  are disjoint files — the project's primary Workflow candidate; re-check the §7
  rubric before fanning out). **`clients/chirps.py` must use `UCSB-CHG/CHIRPS/DAILY`**
  (DEC-013); the deficit logic in `build_baseline._chirps_season_sum` is a working
  reference. **ACLED moved to OAuth/`myACLED`** (legacy key deprecated, S2 handoff)
  — `acled.py` needs a token exchange, not a key query string.
- Baseline is ready for **S8 food-security** (needs validated S6/S7 first): read
  the 4 study-AOI rows of `production_baseline.csv` as the per-AOI 2025 reference,
  and `ndvi_anomaly_2025.tif` / `rainfall_deficit.csv` as drought context.
- **Reuse for S6/S7 raster pulls:** the geedim export + local-mask pattern in
  `build_baseline.build_ndvi_anomaly` (bilinear reproject when a `.max()`/composite
  loses its projection; local cropland masking via `reproject` onto the tile grid)
  is the template for flood/burn rasters.

**Gotchas carried forward (still true):**
- A single `reduceRegions`/large `reduceRegion` at 30 m over a whole governorate (or
  all 14) **times out** server-side — loop per-feature and/or sample coarser
  (300 m) for ratios; pull rasters tile-by-tile via geedim.
- `.max()`/mosaic composites have **no fixed default projection** → `reduceResolution`
  fails ("valid default projection"); use `resample('bilinear')` + `reproject` instead.
- geedim fills out-of-mask/out-of-polygon pixels with **0, not nodata** — enforce the
  authoritative cropland/polygon mask **locally** after download (done here).
- `conda run -n f_f python -c "<multiline>"` still fails on newlines; backgrounded
  `conda run` buffers stdout until exit (tqdm writes `\r` to stderr). Filter the
  benign `gdk-pixbuf`/librsvg warning. Temp scripts go in gitignored `secrets/`.

---

## Session 5: W3 — API clients (FIRMS, CHIRPS, ACLED, HDX/ReliefWeb)

**Objective:** Build the cached, checkpointed external-source clients that the pipelines and RQ analyses pull through.
**Inputs:** `docs/STRUCTURE.md` §5 (access methods), §9 (caching/rate-limit rules); the dossier (S2); `clients/{firms,chirps,acled,hdx}.py` stubs.
**Outputs:** Working `clients/firms.py`, `clients/chirps.py`, `clients/acled.py`, `clients/hdx.py` — each cached, checkpointed, rate-limit aware, with unit tests.
**Depends on:** S1; S2 recommended (access methods/limits confirmed).
**Branch:** `session/syria-agri-shocks-s5`
**Parallel-eligible task groups:** **Group A — the four clients.** `firms.py`, `chirps.py`, `acled.py`, `hdx.py` are disjoint files, share no modified imports, and touch no shared schema. This meets the §7 parallel rubric and is the project's primary Workflow candidate. The executor must re-check the rubric against the actual files before fanning out; parallel execution is opt-in. **Caching/retry behavior is Tier-1 agent-verifiable** (no Tier-2 gate here).

### Context for resumption

§9 is non-negotiable for these clients: **all external pulls are cached and checkpointed** — for rate-limit safety (FIRMS 5,000/10 min, ACLED tiers) and reproducibility, and so retry loops **never re-pull**. FIRMS uses VIIRS 375 m, never MODIS for detection (DEC-006); MODIS is monthly burned-area context only. Keys/auth come from env (`MAP_KEY`, ACLED key) — never hard-coded. Each client is an independent file; this is the one session where fan-out is appropriate.

### Steps

1. `firms.py`: `MAP_KEY` from env; query VIIRS hotspots per fire AOI/window; cache responses; expose rate-limit headroom.
2. `chirps.py`: pull CHIRPS daily over AOIs/windows (used by baseline, floods context, and RQ1); cache.
3. `acled.py`: keyed client for conflict events over AOIs/windows (RQ2); respect tier limits; cache.
4. `hdx.py`: HDX/ReliefWeb pulls for corroborating reports; cache.
5. Unit-test each client's cache hit/miss and "no re-pull on retry" behavior with mocked responses.

### Completion criteria

- [x] Each client reads its key/config from env **and `secrets/secrets.toml`** (DEC-020) and fails clearly when absent (`ConfigError` with remedy; unit-tested).
- [x] Each client caches and checkpoints; a simulated retry does **not** re-pull (unit-tested per client + live-verified for FIRMS/ACLED/CHIRPS).
- [x] FIRMS client uses VIIRS 375 m (not MODIS); rate-limit headroom is surfaced (`rate_limit_headroom()`, local rolling-window tracker).
- [x] Unit tests pass for all four clients — **22 passed** (`pytest clients/`), Tier-1 self-certified.

### Handoff notes

**Status: COMPLETE (2026-06-12).** All four clients built on one shared
config+cache layer, unit-tested (22 Tier-1 tests pass), and **live-verified**
against the real APIs for FIRMS, ACLED, CHIRPS, and HDX. Tier-1 only — no Tier-2
gate. DEC-020 (secrets.toml + cache design) and DEC-021 (confirmed access models)
logged.

**What was built / changed:**
- **`clients/_common.py`** (new) — the shared layer (DEC-020): `secret()` (env →
  secrets.toml → `ConfigError`), `Cache` (one file per request unit under
  gitignored `cache/<ns>/`; `.cached()` is the §9 no-re-pull checkpoint),
  `RateLimiter` (persisted rolling-window budget; only real fetches consume it),
  and `load_aois()`/`aoi_bbox_str()` (stdlib-JSON AOI loader so bbox clients need
  no geopandas; §3.1 — no AOI redefined).
- **`clients/firms.py`** — VIIRS 375 m area API (DEC-006/021). Window split into
  ≤10-day chunks × 3 VIIRS NRT products (`*_SP` for archive); each chunk a cache
  unit. `rate_limit_headroom()` surfaces the 5,000/10-min budget (multi-day = N
  transactions). Live: **103 detections over Hasakah** 06-08..10, headroom −9,
  retry fully cached.
- **`clients/chirps.py`** — `UCSB-CHG/CHIRPS/DAILY` (DEC-013) daily AOI-mean precip
  series, reduced server-side in one pass, cached per `(aoi_id,start,end)`. AOI-mean
  not cropland-masked (5.5 km pixels, DEC-017). Live: 10-day Deir ez-Zor pull, retry
  cached.
- **`clients/acled.py`** — myACLED **OAuth2 password grant** (DEC-021): token
  lifecycle (access 24 h / refresh 14 d) cached in `cache/acled/_token.json`
  (never in secrets.toml), 401→refresh→retry, `event_date BETWEEN` filter, per-page
  caching (resume mid-pagination). `ACLED_ADMIN1` pinned to **live** strings
  (`Deir ez Zor`/`Ar Raqqa`/`Al Hasakeh`/`Lattakia`). Live: 256/907 events for
  populated windows.
- **`clients/hdx.py`** — HDX CKAN `package_search` (no key, live) + **GDELT** DOC
  2.0 news API (`search_gdelt`, no key/no listing). **ReliefWeb was dropped**
  (DEC-022): its API is gated to ReliefWeb-listed organizations. GDELT throttles
  to ≤1 req/5 s and caches; unit-test-proven, but a live 200 wasn't obtainable
  from this env's IP (GDELT rate-limited it after the probe burst — re-verify at S8).
- **`clients/test_clients.py`** (new) — 22 hermetic Tier-1 tests (cache, config,
  rate limiter, all four clients; tmp_path-isolated). **`README.md`** §3 rewritten
  for the secrets.toml model. **`tracking/DECISIONS.md`** — DEC-020, DEC-021.

**Two human prerequisites surfaced (not blockers for S5; needed before the
consumers pull live):**
1. **GDELT live re-verification** — ReliefWeb was replaced by GDELT (DEC-022, no
   key needed). The client is unit-test-proven but GDELT rate-limited this env's IP
   during S5, so a live 200 payload wasn't captured here. Re-confirm a live GDELT
   pull from an un-throttled IP when S8 first uses news corroboration. (No human
   credential action — GDELT needs none.)
2. **ACLED data coverage** — the live ACLED archive currently has **no 2026 Syria
   data** (the project's simulated "today" 2026-06-12 is ahead of real ACLED
   coverage), so `fetch_events(..., 2026-…)` returns 0 rows *correctly*. The client
   is proven against 2024/2023 windows. **S10/RQ2 must check ACLED's live max date
   before relying on the 2026 fire-window pull** — if 2026 isn't yet ingested, the
   conflict overlay can't be computed and that's a data-availability gap to flag,
   not a code bug.

**For the next sessions (S6 floods / S7 fires — both depend on S3+S2, not S5):**
- S6/S7 can start now; the only S5 client either consumes is **`firms.py`** (S7
  fires) and **`chirps.py`** (S6 flood context / S9). Call `from clients.firms
  import fetch_hotspots; fetch_hotspots("hasakah", start, end)` — bbox is resolved
  from the canonical AOIs automatically. **FIRMS NRT only covers ~last 2 months**
  — fine for the 2026 windows now, but a much-later re-run needs `VIIRS_*_SP`.
- **CHIRPS client supersedes the inline `build_baseline._chirps_season_sum`** for
  S9/RQ1 — `chirps.fetch_daily()` returns the cached daily series; sum it for the
  season total.
- ACLED (S10) and HDX/GDELT (S8) are ready to import; mind the two notes above.

**Gotchas carried forward (still true):**
- `conda run -n f_f python -c "<multiline>"` fails ("arguments contain newlines") —
  write a temp script (gitignored `secrets/`) and run that; for `clients` imports
  set `PYTHONPATH=.` (the script's own dir is not the repo root).
- Filter the benign `gdk-pixbuf`/librsvg warning on every `conda run`.
- `cache/` and `secrets/` are gitignored — live pulls and creds never commit; a
  clean checkout re-pulls (cache is a reproducibility checkpoint, not a source).

---

## Session 6: W4 — Pipeline A: flood masks → `damaged_cropland_ha` (TIER-2)

**Objective:** Produce per-AOI/per-date flood-extent masks and the flooded-cropland damage records (emitted `unvalidated`), ready for human validation.
**Inputs:** `docs/STRUCTURE.md` §4 (Pipeline A), §3.2 (schema), §6 (validation), §9; `aois/` (S3); verified GEE IDs (S2); `chirps.py` (S5, context); `pipelines/floods/{flood_mask,cropland_flooded}.py`.
**Outputs:** Flood-extent masks per AOI/date; `DamageRecord`s with `phenomenon=flood`, `validation_status=unvalidated`, written in the canonical table format.
**Depends on:** S3 (AOIs/mask); S2 (IDs). Independent of S7.
**Branch:** `session/syria-agri-shocks-s6`
**Parallel-eligible task groups:** **Mask generation may fan out per sub-AOI** (Deir ez-Zor, Raqqa, Hasakah are disjoint outputs) — Workflow-eligible for the *generation* step only. **Validation does NOT fan out and is human (Tier-2, DEC-007).**

### Context for resumption

Pinned facts: Sentinel-1 SAR is **load-bearing** (flood extent through cloud); optical (Sentinel-2 + Dynamic World) is **confirmatory only** (§9, DEC-006). Subtract permanent water using JRC Global Surface Water. Window March–June 2026 (April floods/hail + late-May Euphrates surge); AOIs Deir ez-Zor, Raqqa, Hasakah. Every output `DamageRecord` defaults to `unvalidated`; **no agent/Workflow run may set it to `validated`** (§6). The food-security and RQ sessions will refuse to consume anything not human-validated, so this session is *not done* until the human gate below is met. Read §4, §6, and `schema/damage_schema.py` first.

### Steps

1. Generate SAR-based flood extent per AOI/date; subtract permanent water (JRC GSW); use optical only to confirm.
2. Intersect flood extent with `aois/cropland_mask.tif`; compute `damaged_cropland_ha` per AOI/date/severity bin.
3. Emit `DamageRecord`s (phenomenon=flood, `validation_status=unvalidated`) in the canonical table format.
4. Prepare a validation packet for the human: masks vs **GloFAS** and any **Copernicus EMS** flood activation for the window (named ground truth, §6).
5. **STOP for human validation.** Record the human verdict (validated/rejected) per record; only the human flips `validation_status`.

### Completion criteria

- [x] Flood masks generated per AOI/date with SAR as primary, permanent water subtracted.
- [x] `damaged_cropland_ha` records emitted, schema-conformant, all `unvalidated` by default (Tier-1: schema conformance is agent-verifiable).
- [x] Validation packet (masks vs GloFAS / EMS activation) assembled.
- [x] **HUMAN GATE (Tier-2):** a human has compared masks against GloFAS + any EMSR flood activation and set `validation_status` accordingly. _Agents/Workflows may not tick this._ **✅ CLOSED by human (2026-06-13):** the user reviewed the validation packet (per-AOI flood-frequency previews, screening series, hectare table) against their domain knowledge, the photos, and the data; found it accurate; and approved all records. All 63 `DamageRecord`s set to `validated` (verdict recorded by the human, transcribed to `validation_status`).

### Handoff notes

**Status: COMPLETE (2026-06-13) — Tier-1 built + Tier-2 human gate CLOSED.** The
SAR flood pipeline runs end-to-end and emits 63 schema-conformant `DamageRecord`s
(21 per AOI × 3 AOIs). The **human reviewed and validated all 63** against the
packet + their own knowledge/photos/data (§6, DEC-007); every record is now
`validation_status=validated` and `is_consumable()=True`, so S8 (food-security)
and S9 (RQ1) may consume them.

**What was built:**
- **`pipelines/floods/flood_mask.py`** (DEC-023) — server-side S1 change-detection
  flood builders. Per S1 date: reference = in-season per-relative-orbit **median**
  (Mar–Jun 2026); flood = VV drop ≥ 4 dB **AND** VV < −18 dB **AND** VH < −24 dB
  (dual-pol open water) **AND** MERIT-Hydro **HAND < 15 m** (floodplain) **AND** not
  JRC GSW permanent **AND** GLO-30 slope < 5°. 50 m focal-mean pre-filter.
- **`pipelines/floods/cropland_flooded.py`** (DEC-024) — orchestration: screen every
  S1 date (coarse 150 m, cached per AOI) → auto-select ≤5 event dates exceeding a
  dry baseline → export the 30 m flood binary per event (geedim, `max_requests=2`
  for Restricted Mode) → local connected-component cleanup, stack to a per-pixel
  flood **frequency**, intersect the **canonical** `aois/cropland_mask.tif`
  (union {1,2,3} and intersection {3}) → emit records → render the validation packet.
- **Outputs:** `outputs/floods/flood_damage.csv` (+ `.parquet`, lossless round-trip
  verified); `outputs/floods/validation_packet/` = 3 per-AOI flood-frequency PNGs,
  `hectare_summary.csv`, `screening_series.csv` (every S1 date + `is_event`), and a
  README pointing at the GloFAS / EMS ground truth and the method caveats.

**The signal (UNVALIDATED — for the human to confirm, not a finding yet):**
- Auto-selected event dates cohere with the documented events and propagate
  **upstream→downstream**: Raqqa flags May 31 + Jun 6/7/8; Deir ez-Zor Jun 2/3/6/7;
  Hasakah (Khabur) Jun 2/3/7 + two March dates. The late-May Euphrates surge
  (PRODUCT §2) is the dominant June cluster.
- Per-AOI/date **persistent** flooded cropland — **intersection** (high-confidence)
  vs **union** (liberal): Deir ez-Zor 907 / 17,320 ha; Raqqa 514 / 30,177 ha;
  Hasakah 1,761 / 19,658 ha. The ~17–50× union:intersection gap is the expected
  DEC-015 DW/WC disagreement spread (worst in Deir ez-Zor, 72 %). Treat the truth
  as bracketed by the two; the human validates extent against GloFAS/EMS.

**Method history (why the first attempt was wrong — see DEC-023):** a dry-summer
reference + single-band lenient threshold flagged ~10⁵ ha of false "flood"
(spring crop phenology + smooth dry **harvested** June fields mimic water in SAR).
The in-season median + dual-pol AND + HAND floodplain gate fixed it; the screening
series in the packet is the evidence the peaks are now event-specific, not noise.

**Caveats carried (proportionate claims, §9):** change-detection on a backscatter
*drop* captures **open standing water**; flooded vegetation (VV double-bounce) and
**pluvial upland** flooding (HAND-excluded) are under-detected. Hectares are
open-water riverine flood extent. Optical/Dynamic World is the confirmatory layer.

**Gate closed (2026-06-13).** Human reviewed the packet + domain knowledge/photos/
data, approved all 63; verdict transcribed to `validation_status=validated`.
*Process note:* the gate field is **`validation_status` in `flood_damage.csv`**
(`unvalidated`→`validated`), NOT the `is_event` True/False column in
`screening_series.csv` (that only flags which S1 dates were processed as events).
A future Tier-2 sign-off should edit `validation_status`; per-record `rejected`
is the path if a subset fails review.

**For S7 (fires) — reusable from here:** the geedim `max_requests=2` Restricted-Mode
export pattern, the screen-cache + tile-cache checkpointing (`_flood_tiles/`), and
the local connected-component cleanup + canonical-mask-reproject accounting all
transfer directly to the burn-severity raster path. **GEE is in Restricted Mode**
(noncommercial compute-quota throttle) — keep concurrency at 2 and lean on caches.

**For S9 (RQ1):** the flood event dates + the cached screening series are the
flood-timing signal to set against GloFAS discharge / CHIRPS rainfall for the
rainfall-vs-release decomposition.

---

## Session 7: W5 — Pipeline B: fire layers → `damaged_cropland_ha` (TIER-2)

**Objective:** Produce active-fire detections and burn-severity scars over cropland, and the burned-cropland damage records (emitted `unvalidated`), ready for human validation.
**Inputs:** `docs/STRUCTURE.md` §4 (Pipeline B), §3.2, §6, §9; `aois/` (S3); verified IDs (S2); `firms.py` (S5); `pipelines/fires/{active_fire,burn_severity}.py`.
**Outputs:** VIIRS hotspot sets + Sentinel-2 dNBR scar/severity per AOI/window; `DamageRecord`s with `phenomenon=fire`, `validation_status=unvalidated`.
**Depends on:** S3 (AOIs/mask); S2 (IDs); S5 (FIRMS client). Independent of S6.
**Branch:** `session/syria-agri-shocks-s7`
**Parallel-eligible task groups:** **Scar/severity generation may fan out per AOI** (Hasakah cropland, Latakia coastal/forest are disjoint). **Validation does NOT fan out and is human (Tier-2, DEC-007).**

### Context for resumption

Pinned facts: **FIRMS VIIRS 375 m for detection, never MODIS** (MODIS MCD64A1 is monthly burned-area context only — DEC-006, §9). Sentinel-2 dNBR gives scar + severity; Dynamic World gives the cropland baseline. Windows: May–July 2026 fire season; **July 2025 Latakia EMSR811** is the documented anchor/precedent (PAX Sentinel-2 methodology). AOIs: Hasakah (cropland fires), Latakia (coastal/forest). Outputs default to `unvalidated`; the human gate below is mandatory before anything downstream consumes them (§6). Read §4, §6, and `schema/damage_schema.py` first.

### Steps

1. Pull VIIRS active-fire hotspots per AOI/window via `firms.py` (cached).
2. Compute Sentinel-2 dNBR scars + severity; intersect with the cropland mask; compute `damaged_cropland_ha` per AOI/window/severity.
3. Emit `DamageRecord`s (phenomenon=fire, `validation_status=unvalidated`) in canonical format.
4. Prepare a validation packet: scars vs **Copernicus EMS EMSR811** and the PAX methodology precedent (named ground truth, §6).
5. **STOP for human validation.** Record verdicts; only the human flips `validation_status`.

### Completion criteria

- [x] VIIRS-based detections + S2 dNBR scars generated per AOI/window (MODIS not used for detection).
- [x] `damaged_cropland_ha` records emitted, schema-conformant, all `unvalidated` (Tier-1: schema conformance agent-verifiable).
- [x] Validation packet (scars vs EMSR811 / PAX precedent) assembled.
- [x] **HUMAN GATE (Tier-2):** a human has compared scars against EMSR811 and set `validation_status` accordingly. _Agents/Workflows may not tick this._ **← CLOSED BY HUMAN 2026-06-13: reviewed `outputs/fire_validation/` against EMSR811 + other sources, judged all three AOIs accurate, set all 8 records `validated` in `outputs/tables/fire_damage.csv`.**

### Handoff notes

**Status: COMPLETE (2026-06-13).** All four criteria met — the Tier-2 human gate is
CLOSED: the human reviewed the validation packet against Copernicus EMS EMSR811 and
other sources, judged all three AOIs accurate, and set **all 8 fire DamageRecords to
`validated`** (schema-verified, all now `is_consumable()`==True). The validated fire
records are ready for S8 (food-security). Tier-2 gate closed by a human, not an agent
(§6/DEC-007).

**Isolation (ran parallel with S6/floods):** S6 was live in `D:\flood_fire` on
`main`; S7 ran in an **isolated git worktree `D:\flood_fire-s7`** on branch
`session/syria-agri-shocks-s7`, with the gitignored prerequisites
(`aois/cropland_mask.tif`, `secrets/`) copied in. Zero contention with S6's tree.
**Merge note:** both sessions edited `tracking/DECISIONS.md` and this plan; expect a
trivial end-of-file textual conflict — keep both blocks (see numbering note below).

**What was built / changed (all in `pipelines/fires/` unless noted):**
- **`active_fire.py`** — VIIRS detection half: cached `fetch()` (via `clients/firms.py`),
  `to_gdf`/`to_ee_points`, `near_fire_mask` (375 m hotspot footprint, the DEC-031
  confirmation), `footprint_geometry` (bounds reduceRegion compute), `summary`,
  `save_hotspots_csv`.
- **`burn_severity.py`** — S2 dNBR engine: `cropland_masks()` (DEC-015 union/inter,
  server-side), `_s2_nbr`/`dnbr_image` (cloud-masked NBR=(B8−B12)/(B8+B12),
  dNBR=pre−post), `severity_class_image` (DEC-009 bins as count-of-thresholds, so it
  inherits dNBR's projection), `burned_cropland_ha` (severity ∩ near-fire ∩ cropland,
  pixelArea grouped by class over the footprint), `cropland_area_ha` (cross-check).
- **`build_fires.py`** — driver. Writes `outputs/tables/fire_damage.{csv,parquet}`
  (8 union-headline records, all `unvalidated`), `fire_damage_sensitivity.csv`
  (union vs intersection), `fire_validation_anchor_emsr811.csv`, and
  `outputs/fire_hotspots/*_viirs.csv`.
- **`generate_packet.py`** — Tier-2 packet: per-AOI context+zoom PNGs in
  `outputs/fire_validation/` + `VALIDATION_PACKET.md` (the human gate instructions).
- **`clients/firms.py`** — **DEC-030 fix:** area-API day-range cap 10→5 (live API now
  rejects >5). **`clients/test_clients.py`** — updated the chunk test to the 5-day cap.
  **30 tests pass** (`pytest clients/ schema/`).
- **`tracking/DECISIONS.md`** — **DEC-030/031/032** (in the reserved fires block).

**Headline results (UNVALIDATED — pending the gate):**
- **Hasakah 2026 (May 1–Jun 12):** 1925 VIIRS hotspots → **3,757.7 ha** burned cropland
  (union; 2,942.9 ha intersection). Severity: low 1335 / mod-low 1569 / mod-high 769 /
  high 84 ha. This is the real 2026 cropland-fire signal.
- **Latakia 2026:** only **9 hotspots → ~1.1 ha**. The 2026 season has barely begun and
  its **July peak is in the simulated future** (today 2026-06-13; VIIRS NRT ends 06-12) —
  a data-availability gap, **not** "no fire risk". Records emitted (mostly 0 ha) and flagged.
- **EMSR811 anchor (Jul 2025 Latakia):** 915 hotspots; the dNBR recovers a large contiguous
  high-severity **forest** scar (see `latakia_2025_emsr811_validation.png`) — only ~17 ha is
  *cropland* (correct: it burned coastal forest). Used to validate the **method**, NOT a
  study record (2025 = baseline/context, DEC-001).

**Key method decisions (within the pinned contracts):**
- **DEC-031 — VIIRS-proximity confirmation:** a dNBR scar counts as fire damage only within
  375 m of a hotspot. Discriminates fire from harvest/plough NBR drops → estimate is a
  **conservative lower bound**. The human judges if it's too strict.
- **DEC-032 — union headline + sensitivity side-table:** the schema has one
  `damaged_cropland_ha` per key, so records carry the **union** (DEC-015 headline) and the
  union/intersection range lives in `fire_damage_sensitivity.csv`. **S6/floods should adopt
  the same convention** so S8 reads one consistent headline column across both phenomena.
- **Cropland equivalence proven:** server-side DEC-015 cropland matches the human-reviewed
  `cropland_mask.tif` — Hasakah union 1.005 / inter 0.999, Latakia within ~5%.

**DEC numbering (parallel-session collision avoidance):** S7 reserved **DEC-030–032** for
fires, leaving **DEC-023–029 for S6/floods**. Disjoint ranges → at merge keep both blocks,
no renumber needed (unless S6 overflowed past DEC-029).

**For the NEXT actions:**
1. **HUMAN (mandatory, Tier-2):** open `outputs/fire_validation/VALIDATION_PACKET.md`,
   download Copernicus EMS **EMSR811** and overlay it on the anchor PNG, review the Hasakah/
   Latakia study panels, then set `validation_status` (`validated`/`rejected`) **per record**
   in `outputs/tables/fire_damage.csv`. Only then is S7 "Complete". Then `--no-ff` merge the
   branch (per the commit-on-session-complete habit).
2. **S8 (food-security)** consumes only `validated` fire records — it cannot run until the gate
   closes. It should read both `fire_damage.csv` (union headline) and
   `fire_damage_sensitivity.csv` (range).
3. **S10/RQ2** reuses these hotspots + the DEC-031 pattern for the ACLED conflict overlay; mind
   the S5 note that **live ACLED has no 2026 Syria data** yet.

**Gotchas carried forward (still true):** `PYTHONPATH=.` for `clients`/`pipelines` imports;
filter the benign `gdk-pixbuf`/librsvg warning on every `conda run`; temp scripts in gitignored
`secrets/`. New: a single `reduceRegion` over a **whole governorate** at 30 m still times out —
reduce over the **hotspot footprint** (dNBR is lazy, only evaluated in the region) and keep the
cropland cross-check at coarse scale (100 m) for Hasakah.

---

## Session 8: W6 — Food-security impact layer

**Objective:** Translate **validated** damage records into production loss and a food-security phase delta against the 2025 baseline.
**Inputs:** `docs/STRUCTURE.md` §3.4 (join contract), §3.3 (baseline), §6 (validated-only gate); `baseline/` (S4); **validated** `DamageRecord`s (S6, S7); GIEWS/FEWS NET/IPC + WFP/FAO ASIS; `food_security/impact_layer.py`.
**Outputs:** Production-loss and food-security phase-delta tables/figures in `outputs/`, joined to GIEWS/FEWS NET/IPC and referenced to the 2025 baseline.
**Depends on:** S4 (baseline), S6 (validated floods), S7 (validated fires).
**Branch:** `session/syria-agri-shocks-s8`
**Parallel-eligible task groups:** None (single integration join over the full validated record set).

### Context for resumption

§3.4 and §6 are pinned and load-bearing here: this layer **consumes ONLY records with `validation_status == validated`** and reads the **shared damage schema only** — never a pipeline's internal rasters (`DamageRecord.is_consumable()` is the gate). If S6/S7 have not been human-validated, this session **cannot proceed** — that is by design, not a blocker to route around. Chain: `damaged_cropland_ha` → estimated production loss → food-security phase delta, referenced to the §3.3 baseline. Read §3.4, §3.3, §6, and `impact_layer.py` first.

### Steps

1. Filter incoming records to `is_consumable()` (validated only); assert/refuse otherwise.
2. Convert `damaged_cropland_ha` → estimated production loss using a documented yield assumption per governorate.
3. Express loss against the §3.3 production floor and map to a food-security phase delta joined to GIEWS/FEWS NET/IPC (WFP/FAO ASIS as available).
4. Write impact tables/figures to `outputs/`; state confidence and caveats (proportionate claims, §9/PRODUCT.md §9).
5. Log the yield/phase-mapping assumptions in `tracking/DECISIONS.md`.

### Completion criteria

- [x] Layer refuses any non-`validated` record (unit-tested against the gate). *(`gate_records(strict=True)` raises `ValidationGateError`; tests `test_gate_refuses_unvalidated_record`, `test_gate_refuses_rejected_record`, `test_compute_impact_refuses_unvalidated_csv`.)*
- [x] Production-loss → phase-delta chain documented and joined to GIEWS/FEWS NET/IPC vs the 2025 baseline. *(ha → loss at 2025 baseline yield → loss-%-of-baseline → indicative non-IPC pressure band; GIEWS/FEWS NET/IPC named as authoritative phase sources. `impact_by_aoi.csv`, `impact_national.csv`.)*
- [x] Impact outputs in `outputs/` carry explicit confidence/caveats. *(`IMPACT_README.md` + `caveat_footer` on the figure: conservative-yield lower bound, not-an-IPC-phase, pipeline caveats inherited.)*
- [x] Yield and phase-mapping assumptions recorded in `tracking/DECISIONS.md`. *(DEC-033.)*

### Handoff notes

**Status: COMPLETE (2026-06-13).** Tier-1 — the food-security impact layer joins the
**human-validated** flood (63) + fire (8) records into estimated cereal-production
loss and an indicative food-security pressure vs the 2025 drought baseline. No Tier-2
gate in this session (it *consumes* the closed S6/S7 gates; it sets no
`validation_status`). 12 Tier-1 tests pass (`pytest food_security/`). DEC-033 logged.

**The cross-pipeline drift flagged before S8 is RESOLVED (DEC-033).** The user chose
the **union-headline + intersection-low** convention (the fires single-headline shape,
which avoids the flood double-count footgun). The layer normalises both pipelines on
read: floods select `…+cropland_union` rows (intersection rows = low bound); fires read
the `S2_dNBR` headline (intersection from `fire_damage_sensitivity.csv`, **2026 study
rows only** — 2025 EMSR811 anchor excluded, DEC-001).

**Two load-bearing analytical choices (DEC-033):**
1. **No flood temporal double-count.** Flood records are per event-date; a `persistent`
   pixel recurs across dates, so summing hectares across dates double-counts it. Headline
   flood-affected cropland per AOI = the **peak single event-date** extent
   (transient+persistent) — conservative, matches the S6 headlines. A season-distinct
   reference (`Σ transient + peak persistent`) is the upper bracket.
2. **Conservative drought-floor yield.** Loss = ha × per-AOI 2025 baseline yield
   (~0.223 t/ha, DEC-019). That is the drought-collapse yield, so the loss is a
   **lower bound** — 2026 was a tentative recovery (higher expected yields).

**What was built:**
- **`food_security/impact_layer.py`** — `gate_records` (§6 hard gate), `aggregate_floods`
  / `aggregate_fires`, `load_baseline`, `compute_impact`, `pressure_label`, and the
  table/figure/README writers. Runnable: `PYTHONPATH=. python -m food_security.impact_layer`.
- **`food_security/test_impact_layer.py`** — 12 hermetic Tier-1 tests (gate refusal,
  peak-vs-sum, union/intersection split, fire severity sum, 2026-study-only sensitivity,
  loss arithmetic, pressure bands).
- **Outputs:** `outputs/food_security/impact_by_aoi.csv`, `impact_national.csv`,
  `IMPACT_README.md`; `outputs/figures/w6_food_security_production_loss.png` (PNG
  gitignored per DEC-008 — regenerated from code).

**Headline result (validated):** study-area combined cereal-production loss ≈
**24,400 t** (headline; range **2,650–38,400 t** over cropland-def × temporal
uncertainty) = **4.5%** of the four AOIs' 2025 baseline (≈544 kt) and **~2.0%** of the
national ~1.2 Mt floor. Per AOI: Deir ez-Zor **7.55%** / Raqqa **7.61%** (*significant
incremental stress*), Hasakah **2.74%** (*moderate*), Latakia **0.02%** (*marginal* —
fire only; its July peak is in the simulated future). Floods dominate the loss; fire
adds ~840 t (Hasakah).

**For the next sessions (S9 RQ1 / S10 RQ2 / S11 RQ3 — all independent, validated-only):**
- These do **not** consume this layer's loss numbers; they consume the same **validated**
  `DamageRecord`s plus their own external data (CHIRPS/GloFAS for S9, ACLED for S10,
  `control_areas.geojson` for S11). Use `schema.read_csv` + filter `is_consumable()`
  (or `viz.consumable_records`) — the same gate this layer enforces.
- **S9/RQ1** can reuse the flood **event dates** (the per-AOI peak dates: Deir ez-Zor
  Jun 3, Raqqa Jun 7, Hasakah Jun 7 dominate) as the flood-timing signal against GloFAS
  discharge / CHIRPS rainfall. Mind the proportionate-claims / dam-attribution rule (§9).
- **S10/RQ2:** live ACLED still has **no 2026 Syria data** (S5 note) — check ACLED's max
  date before relying on the 2026 fire-window pull; flag as a data-availability gap if absent.
- **Indicative pressure is NOT IPC** (DEC-033). Any report/figure that cites food-security
  phase must carry that caveat and attribute GIEWS/FEWS NET/IPC.

**Gotchas carried forward (still true):** `PYTHONPATH=.` for `food_security`/`schema`
imports; filter the benign `gdk-pixbuf`/librsvg warning on every `conda run`; temp
scripts in gitignored `secrets/`. New: the figure path uses a non-interactive
matplotlib `Agg` backend and degrades gracefully (returns None) if viz/matplotlib is
absent — the CSV outputs never depend on a plotting backend.

---

### S8 re-run (national) — 2026-06-14 (post-S13)

**Status: COMPLETE (2026-06-14).** Re-ran the food-security layer on the national fire
set (S13/DEC-037) — the prior run was stale (Hasakah-only ~3,758 ha fire + a 4-AOI
coupling that **silently dropped** the 9 new fire-only governorates). DEC-040 logged.

**What changed (Task A):**
- **`baseline/production_baseline.csv`** — `aoi_id` filled for **all 14** govs (canonical
  strings from `governorates.geojson`); `is_study_aoi=True` for the **12 damaged** govs;
  **False** for Latakia + Damascus City (verified-excluded, DEC-038). Cropland/production
  columns unchanged (still sums to the 1.2 Mt floor).
- **`food_security/impact_layer.py`** — `STUDY_AOIS` 4→12; the silent `b is None` skip now
  emits a `UserWarning` naming any damaged gov lacking a study baseline (surface, don't
  drop); README/figure national-aware; DEC-039 first-half-2026 / lower-bound caveat stamped
  (new shared `viz.CAVEATS["case_study_2026h1"]`); figure sorted by loss, 12-label layout.
- **`food_security/test_impact_layer.py`** — +4 tests (16 pass; full suite 76 pass).

**New headline (validated; first-half-2026 lower bound):** study-area (12 govs) cereal-
production loss ≈ **25,925 t** (range **3,471–39,946 t**) = **2.16%** of the 12 study govs'
combined 2025 baseline (≈1.199 Mt) and **2.16%** of the national ~1.2 Mt floor. Floods still
dominate the tonnage (Raqqa 10.3 kt / Hasakah 9.6 kt / Deir ez-Zor 5.0 kt); the 9 new
fire-only govs add ~1.1 kt (each *marginal*). The national fire **footprint** tripled
(~10,533 ha vs 3,758) but its **tonnage** stays modest (drought-floor yield ~0.223 t/ha).

**For S11/S12:** the impact CSVs + figure are refreshed national; the validated record set
is unchanged (this re-run consumed it, set no `validation_status`). S12 should audit the
DEC-040 widening + DEC-038 exclusions alongside the gate.

---

## Session 9: W7 — RQ1: flood attribution (rainfall vs discharge)

**Objective:** Decompose the 2026 flood signal into rainfall-driven vs upstream-dam-release-driven components, with explicit confidence and caveats.
**Inputs:** `docs/PRODUCT.md` §5 (RQ1), §9 (sensitivity); `docs/STRUCTURE.md` §7 (W7); **validated** flood outputs (S6); CHIRPS (S5) + GloFAS; `pipelines/floods/attribution.py`, `analysis/whiplash.py`.
**Outputs:** A rainfall-vs-discharge decomposition (series + written finding) for RQ1 in `outputs/`, with confidence bounds and caveats.
**Depends on:** S6 (validated floods), S5 (CHIRPS), GloFAS access.
**Branch:** `session/syria-agri-shocks-s9`
**Parallel-eligible task groups:** None (single reasoning-heavy analysis). Independent of S10/S11.

### Context for resumption

RQ1 is politically charged (dam attribution) — **keep causal claims proportionate to evidence, attribute sources, never overclaim** (PRODUCT.md §9, CLAUDE.md). Method: discriminate rainfall (CHIRPS) vs upstream discharge (GloFAS) against reported Euphrates flows (~2,000 m³/s vs 200–250 in drought years; spillway gates opened first time in 30+ years — PRODUCT.md §2). Reasoning-heavy and consumes only validated flood records. Read PRODUCT.md §5/§9 and `attribution.py` first.

### Steps

1. Assemble the CHIRPS rainfall series and GloFAS discharge series over the flood window/AOIs.
2. Compare against reported Euphrates flows; attribute the share consistent with rainfall vs upstream release.
3. State the decomposition with explicit confidence bounds and the caveats the data can/can't support.
4. Write the RQ1 finding + series to `outputs/`; log method/assumptions in `tracking/DECISIONS.md`.

### Completion criteria

- [x] Rainfall (CHIRPS) and discharge (GloFAS) series assembled over the correct window. *(CHIRPS daily Jan–Jun 2026 per AOI via `clients/chirps.py`; GloFAS `cems-glofas-historical` intermediate, 5 Euphrates/Khabur reaches, 2026 + 2025 ref, via new `clients/glofas.py`. Series in `outputs/floods/rq1_attribution/`.)*
- [x] A rainfall-vs-discharge decomposition stated with explicit confidence and caveats. *(`RQ1_FINDING.md` + `event_mechanism.csv` + `aoi_decomposition.csv` + figure; per-event mechanism by river geography + rainfall/discharge coincidence; HIGH/MED/LOW confidence per claim.)*
- [x] Claims are proportionate and sourced (no overclaim on dam attribution — PRODUCT.md §9). *(Natural-vs-managed release stated as LOW-confidence "consistent with", no dam-release fraction asserted; spillway report cited as context. DEC-035.)*
- [x] Method/assumptions recorded in `tracking/DECISIONS.md`. *(DEC-034 GloFAS/CDS access; DEC-035 RQ1 method + Hasakah-June flag.)*

### Handoff notes

**Status: COMPLETE (2026-06-13).** Tier-1 (reasoning analysis; no Tier-2 gate — RQ1
consumes validated S6 records read-only, sets no `validation_status`). The rainfall-vs-
discharge decomposition is built, GloFAS is wired live end-to-end, and 9 Tier-1 tests
pass (`pytest pipelines/floods/test_attribution.py`). DEC-034/035 logged.

**What was built / changed:**
- **`clients/glofas.py`** (new, DEC-034) — cached GloFAS discharge client over the EWDS
  (`cems-glofas-historical`, **intermediate** product — consolidated lags ~6 mo and
  doesn't cover June 2026). `area`-subset NetCDF cached under `cache/glofas/` (no re-pull,
  §9); local main-stem cell extraction (max-mean-discharge within a window) at 5 reaches:
  Euphrates border/below-Tabqa/Raqqa/Deir-ez-Zor + Khabur@Hasakah.
- **`pipelines/floods/attribution.py`** (built out from stub, DEC-035) — per-event
  mechanism classifier: discharge-ratio-vs-2025-baseline + CHIRPS rainfall →
  riverine/pluvial/mixed/unexplained, keyed by **draining reach** (transboundary Euphrates
  vs rain-fed Khabur). Writes `RQ1_FINDING.md`, `event_mechanism.csv`,
  `aoi_decomposition.csv`, CHIRPS/GloFAS series CSVs, and
  `outputs/figures/w7_rq1_rainfall_vs_discharge.png` (gitignored, DEC-008).
- **`pipelines/floods/test_attribution.py`** (new) — 9 hermetic Tier-1 tests (mechanism
  rules, baseline fallback, peak-not-sum decomposition, licence-gap degradation).
- **`environment.yml`** += `cdsapi`, `netcdf4` (installed into `f_f`).
- **`secrets/secrets.toml`** — `[CDS/EWDS]` (invalid TOML, `:` seps) reformatted to a
  valid `[cds]` section so `tomllib` parses the file (it would otherwise break every
  client). Key unchanged. **(secrets.toml is gitignored — not committed.)**

**The RQ1 finding (defensible, proportionate §9):**
- **Euphrates AOIs (Deir ez-Zor, Raqqa) = upstream/transboundary — HIGH confidence.** The
  June inundation (the largest, harvest-season damage: Raqqa 44.7k ha union on Jun 7)
  coincides with a sustained **~1,600 m³/s dry-season plateau (~6× the 200–250 drought
  baseline, ~3.3× the 2025 ref)** at **zero local rainfall** → upstream-sourced by
  construction. The natural snowmelt peak (~3,400 m³/s) was in **late March**.
- **Hasakah (Khabur) = two stories.** March = a real **rain-fed Khabur pulse** (138/90 m³/s
  vs ~16 baseline) → regional rainfall. **June = NO water source** (Khabur ~8–12 m³/s,
  *below* baseline; zero rain) yet 25–39k ha "flood" → **flagged as the DEC-023 SAR
  harvest artifact**, not attributed.
- **Natural vs managed upstream release = LOW confidence.** The dry-season sustained/rising
  June plateau + the modeled (~1,600) vs reported (~2,000) gap are *consistent with* a
  managed-release contribution (aligns with the reported first-in-30-yr spillway opening,
  PRODUCT §2) — **no dam-release fraction asserted**.

**⚠ FLAG surfaced for the human (per CLAUDE.md — not silently resolved):** the **Hasakah
June validated S6 flood records** (3 dates, ~25–39k ha) have no identifiable water source
and are mechanistically inconsistent with a flood. RQ1 reads them read-only and excludes
them from attribution; **recommend S6 re-examination and an S12 audit note.** This does
not invalidate the Euphrates flood records or the S8 food-security numbers (S8's headline
loss is Euphrates/Deir-ez-Zor/Raqqa-dominated; Hasakah was the smaller contributor), but
the Hasakah flood hectares should be revisited.

**For the next sessions (S10 RQ2 / S11 RQ3 — independent, validated-only):**
- **GloFAS/CDS is now wired** — `clients/glofas.py` + `secrets.toml [cds]` + licence
  accepted. Not needed by S10/S11, but available.
- **S10/RQ2** (fire–conflict) still faces the S5 note: **live ACLED has no 2026 Syria
  data** — check ACLED's max date before the 2026 fire-window pull; flag as a data gap if
  absent. Reuse S7 hotspots + the DEC-031 proximity pattern.
- **S11/RQ3** consumes validated damage + `aois/control_areas.geojson` — descriptive only
  (DEC-005). If it includes flood damage, **carry the Hasakah-June flag forward** so the
  overlay doesn't map artifact hectares as real flooding.
- **S12** should add the Hasakah-June flag to its audit and confirm the GloFAS cache
  reproduces from a clean checkout (licence + key required; `cache/glofas/` is gitignored).
- **S12 — decisive Hasakah-June cross-check (datasets vetted 2026-06-13).** To confirm/refute
  the June artifact *without re-running our own SAR* (that would be circular), use an
  **independent** flood product on the 3 flagged dates (06-02/03/07) over the flagged pixels:
  (1) **Copernicus GFM** — independent Sentinel-1 ensemble (TU Wien/DLR/LIST) with
  reference-water + exclusion layers that suppress exactly the dry-soil false positive (openEO
  `ensemble_flood_extent`); (2) **Copernicus EMS activations** — a web search (2026-06-13)
  found **no** EMS activation for this flood, so authoritative delineation vectors are likely
  unavailable (unlike EMSR811 for the fire gate) — re-check, but treat GFM + Sentinel-2 as the
  primary cross-checks; (3) **Sentinel-2 optical** on the June dates via GEE — cloud-free
  bare/harvested soil vs standing water settles it directly. Expected: flood present in March,
  absent in June. Documentary anchors (verified 2026-06-13): FEWS NET reports ~1,500 ha cropland
  inundated **across all three flood governorates combined** in March (≈ our intersection sum
  ~3.2k ha, ~30× below our union ~48.7k ha — supports truth-at/below-intersection); IFRC #7847
  and the OCHA Flash Update (~1,436 families) are user-cited but were not machine-readable in
  this check (JS-rendered / HTTP 403) — confirm directly. **Already in-repo / redundant for this question:** our own S1 mask
  (DEC-023), GloFAS (DEC-034), HDX client (W3). **Out of scope (PRODUCT non-goals):** ML/CV
  flood models, MODIS for detection, operational/Streamlit dashboards.

**Gotchas carried forward (still true):** `PYTHONPATH=.` for `clients`/`pipelines`
imports; filter the benign `gdk-pixbuf`/librsvg warning. New: `conda run -m module` needs
`--cwd /d/flood_fire` **and** `PYTHONPATH=/d/flood_fire` together or it can miss the
`pipelines` package; CDS retrieves print verbose INFO/maintenance lines to stderr (filter
them); each CDS job queues server-side ~1–3 min on a cache miss (cached `.nc` thereafter).

---

## Session 10: W8 — RQ2: fire attribution (conflict linkage)

**Objective:** Test whether 2026 crop fires concentrate along conflict frontlines / track military activity, vs accidental/agricultural burning.
**Inputs:** `docs/PRODUCT.md` §5 (RQ2), §9; `docs/STRUCTURE.md` §7 (W8); **validated** fire outputs (S7); ACLED (S5); `pipelines/fires/attribution.py`.
**Outputs:** A fire–conflict overlay with proximity-to-frontline and timing analysis for RQ2 in `outputs/`, with caveats.
**Depends on:** S7 (validated fires), S5 (ACLED).
**Branch:** `session/syria-agri-shocks-s10`
**Parallel-eligible task groups:** None (single reasoning-heavy analysis). Independent of S9/S11.

### Context for resumption

RQ2 method: overlay FIRMS/VIIRS hotspots and Sentinel-2 burn scars (from S7, validated) on ACLED conflict events; analyze proximity-to-frontline and timing. PAX methodology is the named precedent (PRODUCT.md §6). Keep linkage claims proportionate — correlation in space/time is not proof of cause (PRODUCT.md §9). Consumes only validated fire records. Read PRODUCT.md §5/§9 and `fires/attribution.py` first.

### Steps

1. Pull ACLED conflict events over the fire AOIs/window via `acled.py` (cached).
2. Overlay validated hotspots/scars on conflict events; compute proximity-to-frontline and temporal coincidence.
3. Characterize whether fires track conflict vs accidental/agricultural patterns, with caveats.
4. Write the RQ2 overlay + finding to `outputs/`; log method in `tracking/DECISIONS.md`.

### Completion criteria

- [x] ACLED events joined to validated hotspots/scars over the correct AOIs/window. *(Joined over the **2025** demo window — the latest ACLED-covered fire season — because live ACLED has **zero 2026 Syria data** (max event_date 2025-06-13). The 2026 study overlay is reported as a data-availability gap, not computed. DEC-036.)*
- [x] Proximity-to-frontline and timing analysis produced. *(Cropland-restricted spatial null + space-time coincidence (5 km, ±7 d) + daily Spearman; `proximity_summary.csv`, `daily_counts_*_2025.csv`, figure.)*
- [x] Conflict-linkage framed proportionately with explicit caveats (PRODUCT.md §9). *(Cropland null is the load-bearing control; finding states co-location ≠ cause; 2025 fires read as agricultural/seasonal, not conflict-concentrated. `RQ2_FINDING.md`.)*
- [x] Method recorded in `tracking/DECISIONS.md`. *(DEC-036.)*

### Handoff notes

**Status: COMPLETE (2026-06-13).** Tier-1 (reasoning analysis; no Tier-2 gate — RQ2
consumes the validated S7 fire detections read-only, emits no schema records, sets no
`validation_status`). The full fire–conflict attribution method is built, **18 Tier-1
tests pass** (`pytest pipelines/fires/test_attribution.py`; 48 with clients+schema), and
it is **demonstrated end-to-end on the latest ACLED-covered window**. DEC-036 logged.

**The constraint that shaped the session (probed live, 2026-06-13):** the recurring
S5/S7/S9 warning is confirmed — **live ACLED Syria coverage ends 2025-06-13**, exactly
one year behind the simulated "today". So the **2026 study fire window has 0 ACLED
events** and its conflict overlay **cannot be computed**. Per the session decision
("build + demo on latest window"), the method is demonstrated on **May 1 – Jun 13 2025**
(the analogous, fully-covered fire season) over the same fire AOIs, with VIIRS `*_SP`
archive hotspots — framed as a **method demo on baseline/context (DEC-001), not a study
finding**. Re-running over `STUDY_WINDOW` yields the real 2026 result, no code change,
once ACLED ingests 2026 Syria data.

**What was built:**
- **`pipelines/fires/attribution.py`** (DEC-036) — pure-numpy distance core
  (`nearest_distance_km`, temporal-windowed nearest, proximity/coincidence summaries,
  Spearman, event-type composition) + loaders over the cached FIRMS/ACLED clients +
  a **cropland-restricted spatial null** (`cropland_null_distance_km`, samples the
  DEC-015 union mask within each AOI footprint, fixed seed). Driver runs the 2025 demo +
  the 2026 study-window gap check. Run: `PYTHONPATH=. python -m pipelines.fires.attribution`.
- **`pipelines/fires/test_attribution.py`** — 18 hermetic Tier-1 tests (distance maths,
  temporal windowing, proximity fractions, coincidence radius, daily alignment, Spearman
  edge cases, armed-type subset, composition, polygon-coord flattening).
- **Outputs:** `outputs/fires/rq2_attribution/` (`RQ2_FINDING.md`, `proximity_summary.csv`,
  `daily_counts_{hasakah,latakia}_2025.csv`, `conflict_types_near_fire_*_2025.csv`) and
  `outputs/figures/w8_rq2_fire_conflict.png` (gitignored, DEC-008).

**The load-bearing analytical choice — the cropland null.** A bare "% within 5 km" is
indefensible: fires (on cropland) and conflict (in inhabited belts) co-locate by geography
alone. RQ2 compares each fire's distance-to-nearest-**armed**-conflict against the distance
from random *cropland* pixels to the same events. Fires "concentrate along frontlines" only
if closer than that baseline.

**Demonstration finding (2025 — baseline/context, NOT a study result):** in **both** fire
AOIs, crop fires are **no closer** to armed conflict than cropland is in general —
Hasakah 14.8 km (fire median) vs 15.8 km (null); Latakia 4.9 vs 3.6 km; coincidence 2% /
5%; daily ρ=+0.36 / +0.08. Latakia's superficial "55% within 5 km" is exposed by the null
as a **small-AOI geography artifact**, not a frontline signal. So the 2025 cropland fires
read as **agricultural/seasonal, not conflict-concentrated** — the proportionate finding
(§9). Co-location is never asserted as cause; PAX Sentinel-2 is the descriptive precedent.

**⚠ Flag for S12 (CLAUDE.md — not silently resolved):** **RQ2 cannot be completed against
real 2026 conflict data until ACLED ingests 2026 Syria events** (max event_date
2025-06-13). S12 should record this as a known data-availability gap; the method + 2025
demo stand, the 2026 study overlay is deferred. This mirrors the S5 ACLED-coverage note —
it is a real-world data-latency property of the simulated date, not a code bug.

**For the next sessions (S11 RQ3 / S12 verification — both independent of S10):**
- **S11/RQ3** consumes validated damage + `aois/control_areas.geojson`, descriptive only
  (DEC-005). Unrelated to S10. If it includes flood damage, carry the **Hasakah-June flag**
  (DEC-035) forward so artifact hectares aren't mapped as real flooding.
- **S12** should (a) log the **RQ2 ACLED-2026 gap** (above) and the **Hasakah-June flood
  flag** (DEC-035) as known gaps; (b) confirm the RQ2 caches reproduce from a clean
  checkout (FIRMS `*_SP` + ACLED token; `cache/` is gitignored). The 2025 demo hotspots
  are baseline/context, never `DamageRecord`s.

**Gotchas carried forward (still true + new):** `PYTHONPATH=.` for `pipelines`/`clients`
imports; filter the benign `gdk-pixbuf`/librsvg warning. **New:** plain `conda run -n f_f`
(capturing) **crashes on a UnicodeEncodeError** when the script prints non-cp1252 chars
(e.g. `⚠`, `→`, `³`) — use **`conda run --no-capture-output -n f_f`** (streams directly)
for any script that prints unicode, or keep stdout ASCII (the module's `__main__` prints
are ASCII-safe; unicode lives only in the utf-8 files it writes).

---

## Session 11: W9 — RQ3: descriptive damage-vs-control overlay

**Objective:** Map the distribution of 2026 cropland damage relative to indicative control areas — **descriptively only**, with no differential or causal claim.
**Inputs:** `docs/PRODUCT.md` §5 (RQ3, locked descriptive framing), §9; `docs/STRUCTURE.md` §7 (W9), DEC-005; **validated** damage records (S6, S7); `aois/control_areas.geojson` (S3); `analysis/control_differential.py`.
**Outputs:** A descriptive spatial overlay of damage vs indicative control zones in `outputs/`, with prominent contested-boundary caveats.
**Depends on:** S6 and/or S7 (validated damage), S3 (control_areas).
**Branch:** `session/syria-agri-shocks-s11`
**Parallel-eligible task groups:** None. Independent of S9/S10.

### Context for resumption

**Hard framing constraint (DEC-005, PRODUCT.md §5/§9, CLAUDE.md):** RQ3 is **descriptive only** — it maps where damage falls relative to indicative government-controlled and former AANES areas, and **must never** infer that either administration fared better or worse. Boundaries are contested and treated as indicative. The module name `control_differential.py` is legacy — do **not** compute a differential or causal comparison. Read PRODUCT.md §5/§9 and DEC-005 before writing a single sentence of framing.

### Steps

1. Overlay validated `damaged_cropland_ha` on `aois/control_areas.geojson`; tabulate damage by indicative zone descriptively.
2. Produce the overlay figure/table with prominent "boundaries contested / indicative only / no differential claim" caveats.
3. Review every sentence of output framing against DEC-005; strip any comparative/causal language.
4. Log the framing review in `tracking/DECISIONS.md`.

### Completion criteria

- [x] Descriptive overlay of damage vs indicative control zones produced. *(`analysis/control_differential.py`; `damage_by_aoi_zone.csv`, `damage_by_indicative_zone.csv`, `RQ3_FINDING.md`, `outputs/figures/w9_rq3_control_overlay.png` — indicative zones + per-AOI validated-damage bubbles.)*
- [x] Every output statement is descriptive — no differential or causal claim (audited against DEC-005). *(Comparison-free zone labels; "What this is / is not" section; module computes no differential despite the legacy name.)*
- [x] Contested/indicative-boundary caveats are prominent in every artifact. *(`INDICATIVE_CAVEAT` banner on the finding, the figure footer, the per-feature geojson `caveat`; "spans both, unapportioned" for Deir ez-Zor.)*
- [x] Framing review logged in `tracking/DECISIONS.md`. *(DEC-041 — scope held to the 4 control-AOI set; national fire govs out of scope; AOI-granular, schema-only, no apportioning.)*

### Handoff notes

**Status: COMPLETE (2026-06-14).** Tier-1 (descriptive reasoning; no Tier-2 gate — RQ3
consumes validated S6/S7 records read-only, emits no schema records, sets no
`validation_status`). 6 Tier-1 tests pass (`pytest analysis/`). DEC-041 logged.

**The scope decision (the question the task flagged):** `control_areas.geojson` covers only
the 4 original AOIs. **RQ3 stays there** — the 9 national fire-only govs (DEC-037) are out of
geographic scope because control geometry was never drawn for them, and inventing contested
boundaries for them would itself breach DEC-005. Their ~4,987 ha burned cropland is listed
**separately** ("outside indicative control-area coverage", no zone assigned).

**AOI-granularity honesty:** the schema is per-AOI and RQ analyses may not read pipeline
rasters (cross-reference discipline), so **Deir ez-Zor (spans both indicative zones) is
reported unapportioned** — not split. Per-AOI headline ha reuse the food-security
`aggregate_floods`/`aggregate_fires` (pure schema functions).

**Descriptive result (validated, first-half-2026 lower bound):** former_AANES (Raqqa+Hasakah)
83,338 ha flood / 5,348 ha fire; Deir ez-Zor (spans both, unapportioned) 22,166 / 198 ha;
outside-coverage national fire govs 4,987 ha. **Co-located totals, not a comparison** — the
government-only AOIs (Latakia) carry no 2026 damage, so it isn't even a two-sided contrast.

**For S12:** audit the descriptive-only framing (DEC-005) and the scope/cross-reference choices;
the RQ3 outputs are validated-only by construction (same gate as S8).

---

## Session 12: W10 — Verification / reproducibility pass

**Objective:** Cross-check end-to-end consistency, schema conformance, validation-gate integrity, and clean-checkout reproducibility before the work is called done.
**Inputs:** All prior outputs; `docs/STRUCTURE.md` §6 (validation), §9 (conventions), §3.2 (schema); `docs/PRODUCT.md` §6 (success criteria); `tracking/DECISIONS.md`.
**Outputs:** A verification report in `outputs/` (or `tracking/`) confirming reproducibility, schema/validation integrity, and PRODUCT.md §6 success criteria — listing any gaps.
**Depends on:** S8, S9, S10, S11.
**Branch:** `session/syria-agri-shocks-s12`
**Parallel-eligible task groups:** None (a holistic audit).

### Context for resumption

This is the `plan-sessions` verification session (§7 W10). It confirms the product-level definition of done in PRODUCT.md §6: validated hectare estimates per AOI/window for both phenomena, the food-security translation, RQ1/RQ2/RQ3, and **end-to-end reproducibility from a clean checkout** (pinned sources, documented/verified GEE IDs, cached pulls). Crucially, audit the **validation gate**: confirm no `damaged_cropland_ha` consumed downstream was ever `validated` by anything but a human (§6, DEC-007). Read PRODUCT.md §6 and STRUCTURE.md §6 first.

### Steps

1. Re-run from a clean checkout (or simulate): env builds, auth path works, cached pulls don't re-fetch, pipelines reproduce.
2. Audit schema conformance of every `DamageRecord` and confirm the food-security/RQ layers reject non-validated records.
3. Verify every consumed record's `validation_status` traces to a **human** verdict (no agent self-certification).
4. Check each PRODUCT.md §6 success criterion; list gaps as remediation items.
5. Write the verification report; record residual decisions/gaps in `tracking/DECISIONS.md`.

### Completion criteria

- [x] Clean-checkout reproducibility confirmed (env, auth, caching, pinned/verified IDs). *(`repro.*` checks: environment.yml pins the stack; the deterministic schema→food-security→RQ3 chain recomputes from committed CSVs; CSV↔Parquet round-trips lossless; pulls cached/checkpointed; GEE IDs verified (DEC-013), non-interactive auth (DEC-012). The validated damage CSVs+parquets are git-tracked. Tier-2 raster re-gen needs GEE (Restricted Mode, cached).)*
- [x] All `DamageRecord`s schema-conformant; downstream validated-only gate proven by test. *(`schema.conformance` PASS — 63 flood + 48 fire; `gate.refuses_unvalidated` PASS; `analysis/test_verify.py` + `food_security`/`analysis` gate tests.)*
- [x] No downstream-consumed record was validated by anything but a human (audited). *(`gate.no_self_certification` PASS — default UNVALIDATED, `validate_record` cannot promote; validated status traces to the human S6/S7/S13 Tier-2 gates.)*
- [x] PRODUCT.md §6 success criteria checked; gaps listed. *(All six checked: 5 PASS, RQ2 GAP (ACLED-2026, DEC-036). Known gaps recorded: DEC-036, DEC-035 Hasakah-June, DEC-039 case-study scope, DEC-015 cropland spread.)*

### Handoff notes

**Status: COMPLETE (2026-06-14).** Tier-1 holistic audit. Built a **reproducible**
verification module (`analysis/verify.py`) that audits schema conformance, the
validated-only gate (incl. no agent self-certification), deterministic-chain
reproducibility, and the PRODUCT §6 criteria, emitting `tracking/VERIFICATION_REPORT.md`.
**15 PASS · 0 FAIL · 1 GAP** (RQ2 ACLED-2026, known). Guarded by `analysis/test_verify.py`
(no hard FAIL on committed state). 85 tests pass total. DEC-042 logged.

**Verdict:** the study meets its product-level definition of done **as a first-half-2026
case study with lower-bound headline figures** (DEC-039), pending the recommended
post-harvest re-run and field/expert verification. The single non-PASS (§6.4 RQ2) is a
data-availability gap, not a code defect — it re-runs with no code change once ACLED
ingests 2026 Syria.

**Known gaps recorded (surfaced for the human):** RQ2 ACLED-2026 (DEC-036); the
Hasakah-June flood flag (DEC-035 — revisit at the re-run via an independent flood product;
floods still dominate the food-security tonnage via the Euphrates AOIs, so the headline
holds); the first-half-2026 case-study scope (DEC-039); the cropland union/intersection
spread (DEC-015).

---

## Session 13: National fire re-scope (drop Latakia) — inserted post-S10

**Objective:** Re-scope the fire pipeline from 2 AOIs (Hasakah + Latakia) to **national** (all governorates with 2026 cropland fire), after the original fire-AOI choice was challenged and found to be anchored on the 2025 EMSR811 *forest* fire — wrong year and land cover for a 2026 cropland study.
**Inputs:** national 2026 VIIRS scan; `docs/STRUCTURE.md` §3.1/§4; DEC-014/015; the S7 fire pipeline (`pipelines/fires/{active_fire,burn_severity,build_fires}.py`).
**Outputs:** national `aois/governorates.geojson` (14 govs) + national `cropland_mask.tif`; national `outputs/tables/fire_damage.{csv,parquet}` (48 unvalidated records, 12 govs); updated spec §3.1/§4; DEC-037.
**Depends on:** S3/S7 (assets + method). **Branch:** `session/syria-agri-shocks-s13-national-fire`.

### Context for resumption

The fire sourcing was challenged by the user (Syria domain expert): Latakia was a 2025/forest artifact, and 2026 crop fires are elsewhere. A national 2026 VIIRS scan confirmed it — Latakia 9 hotspots/0 cropland; fire is national, Hasakah-dominant. The user authorised a full re-scope (national, all 14 govs) with fire framed as its own drought/heat hazard (no active conflict in 2026 → RQ2 = agricultural/accidental, DEC-036/DEC-037). Method is unchanged from S7; only the AOI scope widened.

### Steps & completion criteria

- [x] Canonical AOIs extended 4→14 (`build_aois.py`, `governorates.geojson`; first 4 `aoi_id`s byte-stable; Homs GeometryCollection normalised).
- [x] Spec §3.1/§4 updated + DEC-037 logged (revising DEC-014/015 fire scope).
- [x] National fire build → **48 unvalidated DamageRecords, 12 govs, ~10,533 ha union** (~6,600 inter). Hasakah 4,124 dominant; corroborates user's 2026 news (Idlib/Daraa/Aleppo).
- [x] National `cropland_mask.tif` (all 14) rebuilt (geedim, mosaic 18587×20592; per-gov cropland px in `_mask_stats.json`).
- [x] Per-governorate validation packet assembled (13 panels + `VALIDATION_PACKET.md`).
- [x] **HUMAN GATE (Tier-2) — CLOSED by the user (domain expert, 2026-06-14):** reviewed the full national packet, judged it "accurate enough to proceed", all 48 records set `validated`. Latakia + Damascus City verified-excluded (DEC-038). Supersedes the old 8-record validated set.

### Handoff notes

**Status: COMPLETE (2026-06-14) — Tier-2 human gate CLOSED.** The fire pipeline is
re-scoped national and the domain-expert user validated all 48 records (12 fire
governorates), superseding the old 2-AOI set. DEC-037 (re-scope), DEC-038 (Latakia/
Damascus City exclusion), DEC-039 (first-half-2026 case-study caveat + post-harvest
re-run + field-verification recommendation) logged.

**What landed:** AOIs 4→14 (`build_aois.py`, `governorates.geojson`; Homs GeometryCollection
normalised); national `cropland_mask.tif`; 48 **validated** fire DamageRecords across 12
governorates, **~10,533 ha union / ~6,613 ha intersection** (Hasakah 4,124 dominant;
corroborates the user's 2026 Idlib/Daraa/Aleppo reporting); 13-panel validation packet;
spec §3.1/§4 updated. Method unchanged from S7 (only the AOI loop widened). 60 tests pass.

**⚠ For the NEXT session (S8 food-security re-run — REQUIRED, not yet done):** the national
fire records (~10,533 ha, ~2.8× the old Hasakah-only 3,758) must flow into food-security.
`food_security/impact_layer.py` is **coupled to the 4 original study AOIs**: `STUDY_AOIS`
(4) and `load_baseline()` filters `is_study_aoi == true` (only 4 flagged in
`baseline/production_baseline.csv`). The re-run needs: (a) widen the study AOIs to the 12
fire governorates (all 14 are already in `production_baseline.csv` with cropland-share
disaggregation, DEC-019 — just flag/include them), (b) update `STUDY_AOIS`, (c) re-run +
update `food_security/test_impact_layer.py`. Log it as a decision (the food-security study
area widens national).

**Case-study caveat (DEC-039) — applies study-wide:** windows cover only **first-half 2026**
(fires May 1–Jun 12; the summer harvest-fire peak is unobserved). All headline figures are
**lower bounds**; re-run after the season (≈ Jul–Aug 2026) for the concluded full-year result.
Stamp this caveat on every headline output/report. Field/expert verification preferred for
the conclusive research.

---

## Decision & Change Log

The canonical decision log for this project is **`tracking/DECISIONS.md`** (seeded with locked decisions DEC-001…007). Record all execution-time decisions there, not here, to avoid drift. This table is intentionally left as a pointer.

| # | Session | Decision | Affects |
|---|---------|----------|---------|
| — | — | See `tracking/DECISIONS.md` | — |

## Progress Tracker

| Session | Title | Status | Date | Notes |
|---------|-------|--------|------|-------|
| 1 | W0 — Foundation (env, GEE auth, schema) | Complete | 2026-06-12 | Tier-1; env populated, schema+gee_auth wired, DEC-009/010/011 |
| 2 | Data-source dossier + GEE ID verification | Complete | 2026-06-12 | Dossier written; 8/9 IDs verified, CHIRPS corrected (DEC-013); GEE live via service account (DEC-012) |
| 3 | W1 — AOIs + reconciled cropland mask | Complete | 2026-06-12 | Assets built/verified; DEC-014/015/016. ✅ human mask-review gate PASSED (Tier-2); DW threshold confirmed |
| 4 | W2 — 2025 baseline layers | Complete | 2026-06-12 | Tier-1; 3 layers built+cross-checked; DEC-017/018/019. NDVI px = exact S3 union total |
| 5 | W3 — API clients (FIRMS/CHIRPS/ACLED/HDX+GDELT) | Complete | 2026-06-13 | Tier-1; 4 clients on shared cache/config layer; 23 tests pass; FIRMS/ACLED/CHIRPS/HDX live-verified; ReliefWeb→GDELT (DEC-022); DEC-020/021. ⚠ GDELT live re-verify + ACLED 2026-coverage notes |
| 6 | W4 — Floods → damage | Complete | 2026-06-13 | 63 records (21×3 AOIs); S1 change-det+HAND (DEC-023/024). ✅ **human Tier-2 gate CLOSED** — all 63 `validated`; packet in `outputs/floods/validation_packet/` |
| 7 | W5 — Fires → damage | Complete | 2026-06-13 | **Tier-2 gate CLOSED by human** (all 8 records `validated` vs EMSR811). Hasakah 2026 = 3,758 ha burned cropland (union); Latakia 2026 ≈ 1 ha (July future). DEC-030/031/032. Isolated worktree (parallel w/ S6) |
| 8 | W6 — Food-security impact layer | Complete | 2026-06-13 | Tier-1; validated-only join, 12 tests pass; DEC-033 (union-headline normalisation + flood peak-date no-double-count + conservative drought-floor yield). Study loss ≈24.4 kt (~2.0% of national floor) |
| 8b | W6 re-run — national food-security | Complete | 2026-06-14 | Tier-1; re-run on national fire set (DEC-037). Study area widened 4→12 damaged govs (DEC-040); `production_baseline.csv` flags + `STUDY_AOIS` updated; Latakia/Damascus City excluded (DEC-038); silent-drop now warns; DEC-039 caveat stamped. 16 tests pass. **Study loss ≈25.9 kt (range 3.5–39.9 kt) = 2.16% of national floor; floods dominate, 9 new fire govs add ~1.1 kt** |
| 9 | W7 — RQ1 flood attribution | Complete | 2026-06-13 | Tier-1; CHIRPS vs GloFAS decomposition (new `clients/glofas.py` via EWDS `cems-glofas-historical`); 9 tests pass; DEC-034/035. **Finding:** Euphrates AOIs = upstream/transboundary (June ~1,600 m³/s plateau, 0 rain); natural-vs-managed = LOW conf. **⚠ Hasakah June S6 records flagged: no water source (dry Khabur + 0 rain) → likely DEC-023 SAR harvest artifact — recommend S6/S12 re-exam** |
| 10 | W8 — RQ2 fire attribution | Complete | 2026-06-13 | Tier-1; cropland-null + space-time + temporal overlay; 18 tests pass; DEC-036. **⚠ Live ACLED has no 2026 Syria data (max 2025-06-13) → 2026 study overlay deferred (gap flagged for S12); method built + demonstrated on 2025 window.** Demo finding: 2025 cropland fires **no closer** to armed conflict than cropland baseline → agricultural/seasonal, not conflict-concentrated |
| 11 | W9 — RQ3 descriptive control overlay | Complete | 2026-06-14 | Tier-1; descriptive-only overlay (DEC-041); 6 tests pass. Scope held to the 4 control-AOI set (national fire govs out of scope, ~4,987 ha listed separately); Deir ez-Zor spans both zones, **unapportioned** (AOI-granular, schema-only). No differential/causal claim (DEC-005). `analysis/control_differential.py` + map |
| 12 | W10 — Verification / reproducibility | Complete | 2026-06-14 | Tier-1; reproducible audit (`analysis/verify.py` → `tracking/VERIFICATION_REPORT.md`); **15 PASS · 0 FAIL · 1 GAP** (RQ2 ACLED-2026). Schema conformance, validated-only gate (no self-cert), deterministic-chain repro all confirmed; gaps DEC-036/035/039/015 recorded; DEC-042. 85 tests pass. Verdict: DoD met as first-half-2026 case study (lower bounds) |
| 13 | National fire re-scope (drop Latakia) | Complete | 2026-06-14 | **Tier-2 gate CLOSED by human** (all 48 records `validated`, 12 govs, ~10,533 ha union; Hasakah 4,124 dom.; corroborates 2026 news). AOIs 4→14; national cropland mask; DEC-037/038/039. Supersedes old 8-record set. **⚠ S8 food-security re-run REQUIRED next** (impact_layer coupled to 4 AOIs). Case-study caveat: first-half-2026, lower bound, re-run post-harvest |
