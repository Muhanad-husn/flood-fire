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

- [ ] `syria-2026-agri-shocks-dossier.md` exists with every source's access method, limits, license, and caveats.
- [ ] Every GEE ID in §5 is marked verified-against-live-catalog (with date) or flagged corrected.
- [ ] Named validation ground truth (EMSR811, GloFAS, PAX precedent) documented for both phenomena.
- [ ] Any ID/source discrepancy vs §5 surfaced to the human (not silently resolved).

### Handoff notes

_(filled in during execution)_

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

- [ ] `governorates.geojson`, `cropland_mask.tif`, `control_areas.geojson` exist with a single consistent CRS/resolution, sourced and documented.
- [ ] Cropland-mask Dynamic World vs WorldCover disagreement is documented (§3.1, §9).
- [ ] `control_areas.geojson` carries explicit indicative/descriptive/contested provenance.
- [ ] **Human review** of the cropland mask against known agricultural extent (the mask underpins every `damaged_cropland_ha`; confirm it is not obviously wrong before pipelines consume it).
- [ ] Reconciliation rule recorded in `tracking/DECISIONS.md`.

### Handoff notes

_(filled in during execution)_

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

- [ ] All three baseline artifacts exist, masked/keyed to the canonical AOIs.
- [ ] Rainfall deficit covers exactly Nov 2024–May 2025; NDVI normal period documented.
- [ ] Production floor disaggregation method documented and sums to the GIEWS national floor.
- [ ] Baseline magnitudes are consistent with `docs/PRODUCT.md` §2; assumptions logged in `tracking/DECISIONS.md`.

### Handoff notes

_(filled in during execution)_

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

- [ ] Each client reads its key/config from env and fails clearly when absent.
- [ ] Each client caches and checkpoints; a simulated retry does **not** re-pull (unit-tested).
- [ ] FIRMS client uses VIIRS 375 m (not MODIS); rate-limit headroom is surfaced.
- [ ] Unit tests pass for all four clients (Tier-1 — agent may self-certify).

### Handoff notes

_(filled in during execution)_

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

- [ ] Flood masks generated per AOI/date with SAR as primary, permanent water subtracted.
- [ ] `damaged_cropland_ha` records emitted, schema-conformant, all `unvalidated` by default (Tier-1: schema conformance is agent-verifiable).
- [ ] Validation packet (masks vs GloFAS / EMS activation) assembled.
- [ ] **HUMAN GATE (Tier-2):** a human has compared masks against GloFAS + any EMSR flood activation and set `validation_status` accordingly. _Agents/Workflows may not tick this._

### Handoff notes

_(filled in during execution)_

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

- [ ] VIIRS-based detections + S2 dNBR scars generated per AOI/window (MODIS not used for detection).
- [ ] `damaged_cropland_ha` records emitted, schema-conformant, all `unvalidated` (Tier-1: schema conformance agent-verifiable).
- [ ] Validation packet (scars vs EMSR811 / PAX precedent) assembled.
- [ ] **HUMAN GATE (Tier-2):** a human has compared scars against EMSR811 and set `validation_status` accordingly. _Agents/Workflows may not tick this._

### Handoff notes

_(filled in during execution)_

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

- [ ] Layer refuses any non-`validated` record (unit-tested against the gate).
- [ ] Production-loss → phase-delta chain documented and joined to GIEWS/FEWS NET/IPC vs the 2025 baseline.
- [ ] Impact outputs in `outputs/` carry explicit confidence/caveats.
- [ ] Yield and phase-mapping assumptions recorded in `tracking/DECISIONS.md`.

### Handoff notes

_(filled in during execution)_

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

- [ ] Rainfall (CHIRPS) and discharge (GloFAS) series assembled over the correct window.
- [ ] A rainfall-vs-discharge decomposition stated with explicit confidence and caveats.
- [ ] Claims are proportionate and sourced (no overclaim on dam attribution — PRODUCT.md §9).
- [ ] Method/assumptions recorded in `tracking/DECISIONS.md`.

### Handoff notes

_(filled in during execution)_

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

- [ ] ACLED events joined to validated hotspots/scars over the correct AOIs/window.
- [ ] Proximity-to-frontline and timing analysis produced.
- [ ] Conflict-linkage framed proportionately with explicit caveats (PRODUCT.md §9).
- [ ] Method recorded in `tracking/DECISIONS.md`.

### Handoff notes

_(filled in during execution)_

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

- [ ] Descriptive overlay of damage vs indicative control zones produced.
- [ ] Every output statement is descriptive — no differential or causal claim (audited against DEC-005).
- [ ] Contested/indicative-boundary caveats are prominent in every artifact.
- [ ] Framing review logged in `tracking/DECISIONS.md`.

### Handoff notes

_(filled in during execution)_

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

- [ ] Clean-checkout reproducibility confirmed (env, auth, caching, pinned/verified IDs).
- [ ] All `DamageRecord`s schema-conformant; downstream validated-only gate proven by test.
- [ ] No downstream-consumed record was validated by anything but a human (audited).
- [ ] PRODUCT.md §6 success criteria checked; gaps listed.

### Handoff notes

_(filled in during execution)_

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
| 2 | Data-source dossier + GEE ID verification | Not started | | Reference; precede S6/S7 |
| 3 | W1 — AOIs + reconciled cropland mask | Not started | | Human-reviewed mask |
| 4 | W2 — 2025 baseline layers | Not started | | Compute-heavy |
| 5 | W3 — API clients (FIRMS/CHIRPS/ACLED/HDX) | Not started | | **Parallel-eligible** |
| 6 | W4 — Floods → damage | Not started | | **Tier-2 human gate** |
| 7 | W5 — Fires → damage | Not started | | **Tier-2 human gate** |
| 8 | W6 — Food-security impact layer | Not started | | Validated-only |
| 9 | W7 — RQ1 flood attribution | Not started | | Reasoning-heavy |
| 10 | W8 — RQ2 fire attribution | Not started | | Reasoning-heavy |
| 11 | W9 — RQ3 descriptive control overlay | Not started | | Descriptive only |
| 12 | W10 — Verification / reproducibility | Not started | | Audit gate |
