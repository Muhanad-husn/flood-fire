# Decision & Change Log

Seeded from `docs/STRUCTURE.md` §10 (locked decisions — do not reopen). Record new
decisions below the seed as continued planning and implementation proceed. When
proposing a revision to a locked decision, state what changes, why it's better,
and the downstream impacts; reference the original entry.

## Locked decisions (seed — docs/STRUCTURE.md §10)

- **DEC-001** — Scope is 2026 events; all pre-2026 data is baseline/context only.
- **DEC-002** — Two phenomena, two parallel pipelines, one repo, one shared damage schema.
- **DEC-003** — No deep-learning/CV pipeline; no earthquake analysis.
- **DEC-004** — Primary question is food-security impact vs the 2025 drought baseline.
- **DEC-005** — Secondary questions: flood attribution (RQ1), fire attribution (RQ2), and a descriptive damage-vs-control overlay (RQ3 is descriptive only — never a differential or causal claim).
- **DEC-006** — Sentinel-1 SAR is the primary flood sensor; FIRMS VIIRS the primary fire-detection sensor.
- **DEC-007** — Human-in-the-loop validation is mandatory for all Tier-2 outputs; agents cannot self-certify them.

## New decisions

- **DEC-008** — **Presentation layer = a static, reproducible Quarto report**
  (`report/`), published as self-contained HTML to GitHub Pages; **Streamlit (and
  any running-server dashboard) explicitly rejected.**
  - *Why:* the project is portfolio/publication output and explicitly **not** an
    operational/real-time tool (`docs/PRODUCT.md` §4); reproducibility is a
    first-class success criterion (§6). A static report needs no host, is
    version-controlled, renders offline from a clean checkout, and is the credible
    artifact the audience reads. Streamlit's strengths (live interactivity) serve
    the operational shape this project disclaims, at a hosting/upkeep cost.
  - *Stack:* `seaborn` (charting) on `matplotlib` (axis-level control), `geopandas`
    + `contextily` for static thematic maps, self-contained `folium`/`leafmap`
    Leaflet embeds where reader pan-zoom helps; `geemap` notebooks (`notebooks/`)
    as the exploration + Tier-2 validation workbench (doubles as the gate surface,
    §6). Shared look + enforced rules in `viz/style.py`.
  - *Rules carried in code:* Quarto `freeze: auto` so rendering never re-triggers
    GEE pulls (§9); report figures consume only `is_consumable()` records via
    `viz.consumable_records()` (§6); caveats stamped via `viz.caveat_footer()`
    (RQ3 contested boundaries, attribution uncertainty — §5, §9).
  - *Downstream:* W6–W9 figure functions live with their modules and import `viz`;
    a report page per analysis is filled in as validated outputs land (S8–S12).
    `environment.yml` adds the viz deps; Quarto is a system install.

- **DEC-009** (S1/W0) — **`severity_class` vocabulary pinned per phenomenon** in
  `schema/damage_schema.py` (`SEVERITY_CLASSES`), enforced by `validate_record()`.
  - *Floods:* `transient` (single-date SAR inundation), `persistent` (multi-date
    standing water), `permanent_excluded` (JRC GSW permanent river — subtracted,
    a zero-damage exclusion class, not damage).
  - *Fires:* `unburned | low | moderate_low | moderate_high | high`, following the
    conventional Sentinel-2 dNBR thresholds (Key & Benson / USGS FIREMON:
    dNBR <0.10 / 0.10 / 0.27 / 0.44 / 0.66). `unburned` is a zero-damage class.
  - *Why:* the schema is the single integration contract (§3.2); pinning the vocab
    here lets the food-security/RQ layers group and weight by severity without
    reading pipeline internals. `permanent_excluded`/`unburned` are asserted to
    carry `damaged_cropland_ha == 0.0` so the exclusion is explicit in the table.
  - *Downstream:* W4 (floods) emits flood bins; W5 (fires) emits dNBR bins; both
    must use only these strings. Revisit here (not in code) if a pipeline needs a
    finer bin.

- **DEC-010** (S1/W0) — **Canonical `outputs/` table format = CSV (interchange) +
  Parquet (typed/compact)**, with a lossless round-trip in `schema.damage_schema`
  (`write_csv`/`read_csv`, `write_parquet`/`read_parquet`; columns = dataclass
  field order, enums stored as `.value`).
  - *Why:* CSV is git-/human-friendly and dependency-free (the schema core imports
    no geo/pandas deps); Parquet is the typed, compact form for pipeline I/O.
    Both round-trip identically so either may be the on-disk form. `__post_init__`
    coerces string columns back into the `Phenomenon`/`ValidationStatus` enums so a
    read record `==` the written record. Tier-1 tests in `schema/test_damage_schema.py`.
  - *Downstream:* every module that writes `DamageRecord`s to `outputs/` uses these
    helpers rather than ad-hoc serialization.

- **DEC-011** (S1/W0) — **GEE billing project comes from the `EE_PROJECT` env var**
  (`clients/gee_auth.initialize()`), never hard-coded; `initialize()` is idempotent
  and never launches the interactive auth flow or re-auths in a retry loop (§9).
  - *Why:* §8 auth is human-run once (`earthengine authenticate`); the code path
    only initializes a cached session and fails loudly with the exact remedy when
    credentials are absent. Keeps secrets/config out of the repo and retry loops
    rate-limit-safe.
  - *Downstream:* every GEE-touching module calls `gee_auth.initialize()` once at
    entry; first-run steps documented in the root `README.md`.

- **DEC-012** (S2) — **GEE auth supports a service-account key as the preferred,
  non-interactive path** (`clients/gee_auth.py`), falling back to cached user
  credentials (DEC-011). Key discovery: `EE_SERVICE_ACCOUNT_KEY` env var, else a
  single `service_account`-type JSON in `secrets/` (gitignored). Project defaults
  to the key's `project_id` when `EE_PROJECT` is unset.
  - *Why:* Google is **blocking the `drive` OAuth scope for the default Earth
    Engine client ID**, so the interactive `earthengine authenticate` flow was
    failing at sign-in on this machine. A service account sidesteps the consent
    screen entirely, is fully non-interactive (satisfies DEC-011's "never launch
    the interactive flow in code"), and directly serves S12's clean-checkout
    reproducibility criterion (PRODUCT §6). Verified live: initialized project
    `rich-stratum-429021-u4` and read real S1/CHIRPS/WorldCover data 2026-06-12.
  - *Extends, does not reopen, DEC-011:* the `EE_PROJECT`/idempotent/no-retry-auth
    contract is unchanged; the service-account branch is an added non-interactive
    source. Key lives in `secrets/` (now wholly gitignored — see note below).
  - *Downstream:* a clean checkout needs only the key file (or
    `EE_SERVICE_ACCOUNT_KEY`); no browser step. README first-run note to be
    updated to mention the service-account option (carry into a later session).
  - *Security:* `.gitignore` updated to ignore the entire `secrets/` dir — the
    service-account filename (`<project>-<hash>.json`) matched none of the prior
    patterns and would otherwise have been committable.

- **DEC-013** (S2) — **CHIRPS daily GEE ID corrected to `UCSB-CHG/CHIRPS/DAILY`**
  (hyphen), replacing §5's `UCSB/CHG/CHIRPS/DAILY` (all slashes), which **does not
  resolve** in the live catalog (2026-06-12). **Drift vs `docs/STRUCTURE.md` §5 is
  flagged here, not silently edited in §5** (Working Rules / CLAUDE.md).
  - *Evidence:* `ee.data.getAsset("UCSB/CHG/CHIRPS/DAILY")` → *asset not found*;
    `UCSB-CHG/CHIRPS/DAILY` loads — 31 daily images Jan 2025, band `precipitation`,
    ~5566 m, real value over Deir ez-Zor. The provider namespace is `UCSB-CHG`.
  - *Downstream:* S4 (`baseline/rainfall_deficit.csv`) and S5 (`clients/chirps.py`)
    must use `UCSB-CHG/CHIRPS/DAILY`. **Human action:** decide whether to update
    `docs/STRUCTURE.md` §5 to the corrected ID (recommended) or annotate it.
  - *Other §5 IDs:* the remaining 8 verified exactly as written (see dossier §2).
    Note `JRC/GSW1_4/GlobalSurfaceWater` is an **Image**, not a collection; the GEE
    `FIRMS` collection is **MODIS-derived** (VIIRS detection stays on the API).

- **DEC-014** (S3/W1) — **Canonical AOIs from FAO GAUL 2015 level 1.**
  `aois/governorates.geojson` is built from `FAO/GAUL/2015/level1`
  (`ADM0_NAME == "Syrian Arab Republic"`), four AOIs by `ADM1_NAME`:
  `Dayr_Az_Zor`→deir_ez_zor, `Raqqa`→raqqa, `Hassakeh`→hasakah, `Lattakia`→latakia.
  Stored EPSG:4326 (GeoJSON/CRS84) with `aoi_id, name, gaul_adm1, area_km2,
  pipelines` properties. Areas: Deir ez-Zor 27,307 / Raqqa 17,906 / Hasakah 22,758
  / Latakia 2,429 km².
  - *Why:* GAUL is a single authoritative, GEE-native admin source (no external
    download, reproducible from a clean checkout). `aoi_id` strings are the stable
    keys the shared schema's `aoi_id` field (§3.2) references; no module redefines
    them (§3.1). Pipeline tags encode §4 (floods: DeZ/Raqqa/Hasakah; fires:
    Hasakah/Latakia).
  - *Downstream:* every module loads these geometries; pipelines clip detection to
    them. Generator: `aois/build_aois.py`.

- **DEC-015** (S3/W1) — **Cropland mask = one categorical reconciliation raster,
  30 m, EPSG:32637 (UTM 37N), built UNION-first with disagreement encoded in-band.**
  `aois/cropland_mask.tif`: `0`=neither, `1`=WorldCover-only, `2`=DynamicWorld-only,
  `3`=both agree, `255`=outside AOI (nodata). **Cropland = value ∈ {1,2,3} (union,
  headline); value == 3 = intersection (conservative).** Sources (verified S2):
  ESA WorldCover v200 **class 40**; Dynamic World **annual-mean `crops` prob > 0.35**
  over 2021 (WorldCover v200 reference year). 10 m→30 m via **mode** reduceResolution;
  each AOI **clipped to its polygon** then mosaicked.
  - *Why:* §3.1 mandates "one mask… with disagreement documented" — encoding the
    DW/WC agreement as the pixel value documents disagreement *in the same artifact*
    (classes 1,2 are the disagreement; 3 is agreement), and lets downstream weight
    union vs intersection without reading pipeline internals. Union is the headline
    so cropland (hence damage) is not silently under-counted; intersection is kept
    for a sensitivity bound. 30 m balances fidelity (riparian Euphrates cropland)
    against the export constraint that the **Drive OAuth scope is blocked** (DEC-012),
    so masks are pulled tile-by-tile via getPixels (geedim) where 10 m full-extent
    is impractical. UTM 37N gives metric pixels (0.09 ha each) for honest area sums;
    Latakia sits at the zone's western edge (<0.1% area distortion — acceptable).
  - *DW threshold is a judgement call:* `crops>0.35` is conservative; WorldCover is
    far more liberal (esp. rainfed/fallow Deir ez-Zor), driving a large union-vs-
    intersection spread — see `aois/MASK_DISAGREEMENT.md`. Revisit the threshold here
    (not in code) if the human review finds it mis-calls the agricultural extent.
  - *Downstream:* W4/W5 intersect detection with `value ∈ {1,2,3}`; **report damage
    under both union and intersection** as a sensitivity range. Mask is **Tier-2
    human-reviewed** before any pipeline consumes it (§6, DEC-007) — QC surface in
    `outputs/aoi_qc/`.

- **DEC-016** (S3/W1) — **Large GEE rasters are exported via `geedim` (tiled
  getPixels + mosaic), not `Export.image.toDrive`.** Added to `environment.yml`.
  - *Why:* the EE Drive OAuth scope is deprecated/blocked for this project's auth
    (DEC-012), so `toDrive` is unavailable; `geedim` downloads bounded tiles through
    `getPixels` (no Drive) and is fully non-interactive, serving S12 clean-checkout
    reproducibility. Small tiles (`max_tile_dim=1500`) keep per-tile compute under
    EE's "user memory limit"; an export retry loop absorbs transient memory errors.
  - *Downstream:* the same path serves any later raster pull that exceeds the
    single-`getDownloadURL` size cap (baseline NDVI W2, flood/burn rasters W4/W5).

- **DEC-017** (S4/W2) — **CHIRPS rainfall deficit = the Nov 2024–May 2025 season
  total minus a 1991–2020 (30-season) climatological normal of the same Nov–May
  window, reported as AOI-mean (not cropland-masked).**
  `baseline/rainfall_deficit.csv`: columns `aoi_id, name,
  season_total_mm_2024_2025, climatology_mm_1991_2020, deficit_mm, deficit_pct`.
  - *Why AOI-mean, not cropland-masked:* CHIRPS pixels are ~5566 m — far larger
    than a field — so masking the precipitation grid to 30 m cropland is
    meaningless; the AOI mean is the honest meteorological quantity. The window
    is the §3.3-pinned Nov 2024–May 2025. The normal is the WMO-style 30-year
    period, built as the mean of 30 per-season Nov–May sums (start-years
    1991–2020), excluding the 2024/25 drought season.
  - *Result (live, 2026-06-12):* deficits Deir ez-Zor −26.1%, Raqqa −19.8%,
    Hasakah −25.3%, Latakia −23.0%. A ~20–26% rainfall deficit driving a ~60%
    cereal-production collapse (PRODUCT §2) is consistent with rainfed-cereal
    non-linearity near the wilting margin and the loss of the grain-fill window
    — the deficit is the meteorological driver, not the production number itself
    (that comes from GIEWS, [[DEC-019]]).
  - *Downstream:* RQ1 (S9) reuses the CHIRPS series; the deficit is the baseline
    drought reference the 2026 flood "whiplash" is measured against.

- **DEC-018** (S4/W2) — **2025 NDVI anomaly = Sentinel-2 growing-season (Mar–May)
  per-pixel MAX NDVI for 2025 minus the 2019–2024 mean of the same, on cropland
  (union), 30 m EPSG:32637.** `baseline/ndvi_anomaly_2025.tif` (float32,
  nodata −9999). SCL-cloud-masked S2_SR_HARMONIZED; bilinear-resampled then
  reprojected 10 m→30 m (the `.max()` composite has no fixed projection, so
  `reduceResolution` is unavailable — bilinear reproject is used instead).
  Cropland masking is enforced **locally** against `aois/cropland_mask.tif`
  (value ∈ {1,2,3}, [[DEC-015]]), resampled nearest onto the NDVI grid.
  - *Why the 2019–2024 normal (only 6 seasons):* the S2_SR archive does not
    predate ~2017, so a long climatology is impossible from Sentinel-2; the
    NDVI layer carries the **spatial pattern** of cropland drought stress while
    the **long-baseline magnitude** lives in the CHIRPS deficit ([[DEC-017]]) —
    complementary, by design. MAX over Mar–May captures peak winter-wheat
    greenness regardless of acquisition timing (PRODUCT §2 "critical final
    growth stage"). Output is the raw NDVI difference (not a z-score: 6 seasons
    give an unstable std).
  - *Result (live, 2026-06-12):* mean anomaly Hasakah −0.277, Raqqa −0.197,
    Deir ez-Zor −0.142, Latakia −0.054; **87.6% of all cropland pixels are
    negative.** The inland-to-coast gradient tracks the rainfall deficit and the
    drought narrative. Valid cropland px = 26,538,663 = 2,388,480 ha — **exactly**
    the S3 union total, confirming pixel-perfect alignment to the cropland mask.
  - *Downstream:* baseline/context ONLY (DEC-001) — never the subject of analysis;
    a drought-stress reference for the food-security layer (S8) and figures.

- **DEC-019** (S4/W2) — **The FAO/GIEWS ~1.2 Mt 2025 national cereal floor is
  disaggregated across all 14 Syrian governorates by cropland-area share**
  (cropland union hectares per governorate ÷ national total), so the table sums
  exactly to the floor. `baseline/production_baseline.csv`: all 14 GAUL L1
  governorates with `aoi_id`/`is_study_aoi` flags; the 4 study AOIs hold 45% of
  the floor (≈544 kt). Per-governorate cropland area = mean(cropland binary) at
  300 m sampling × governorate area (a single 30 m `reduceRegions` over all 14
  times out server-side; the 300 m fraction is scale-robust and the share is a
  ratio — validated within ~2% against the authoritative 30 m `_mask_stats.json`
  for the study AOIs).
  - *Assumption & limitation (documented):* this assumes **uniform cereal yield
    per cropland hectare** across governorates — the drought hit unevenly, so the
    flat key understates the spatial variance. That variance is captured instead
    by the NDVI anomaly ([[DEC-018]]) and rainfall deficit ([[DEC-017]]) layers;
    a yield-weighted key was rejected to avoid coupling the production baseline to
    those layers' assumptions. Sub-national GIEWS production figures are not in
    the repo; cropland-area share is the transparent, reproducible key. Revisit
    here if governorate cereal statistics become available.
  - *Downstream:* the food-security layer (S8) reads the 4 study-AOI rows as the
    2025 production reference each AOI's 2026 damage is expressed against (§3.4).

- **DEC-020** (S5/W3) — **Client secrets resolve from `secrets/secrets.toml`
  (gitignored) with a per-key env-var override; one shared cache + config layer
  (`clients/_common.py`) backs all four clients.** `secret(section, key, env=…)`
  checks the env var first, then `[section].key` in the TOML, else raises
  `ConfigError` with the remedy. A `Cache` (one file per request unit under
  `cache/<ns>/`, gitignored) is the §9 checkpoint: `Cache.cached()` returns a hit
  **without calling fetch**, so retries/resumes never re-pull. A persisted
  `RateLimiter` tracks rolling-window transaction budgets; only real fetches
  consume it (cache hits don't).
  - *Why TOML + env, not env-only:* the user provides creds as a single
    `secrets/secrets.toml`; the dir is already wholly gitignored (DEC-012). Env
    override keeps the README's `MAP_KEY`/`ACLED_*` convention working and lets
    CI/clean-checkout inject secrets without a file. `tomllib` is stdlib (py3.13)
    — no new dependency.
  - *Why per-request-unit caching:* each `(AOI × window-chunk × source)` (FIRMS),
    `(AOI, start, end)` series (CHIRPS), or page (ACLED) is its own cache file, so
    a partial multi-request pull resumes mid-stream rather than restarting (§9).
  - *Downstream:* every client (and any later external pull) goes through
    `clients._common`; tests point `_cache`/`_limiter`/`_TOKEN_PATH` at `tmp_path`
    for hermetic runs. 22 Tier-1 tests in `clients/test_clients.py` (pytest clients/).

- **DEC-021** (S5/W3) — **Live access models confirmed and pinned for the four
  clients (probed 2026-06-12):**
  - **FIRMS** — area API `…/api/area/csv/{MAP_KEY}/{SOURCE}/{W,S,E,N}/{day_range≤10}/{end_date}`;
    VIIRS 375 m only (`VIIRS_SNPP_NRT`/`VIIRS_NOAA20_NRT`/`VIIRS_NOAA21_NRT`; `*_SP`
    archive), never MODIS (DEC-006). 5,000 transactions/10 min, **a multi-day
    request costs `day_range` transactions** — tracked locally (the legacy
    `mapserver/mk_check` headroom endpoint now 404s; `data_availability/csv` is the
    key-liveness check). NRT coverage is ~last 2 months only (`VIIRS_SNPP_NRT`
    2026-04-28→06-12 at probe time) — the **2026 flood/fire windows are inside NRT**,
    but a re-run months later needs the `*_SP` archive products. Live: 103
    detections over Hasakah, 2026-06-08..10.
  - **ACLED** — OAuth2 **password grant** at `POST /oauth/token`
    (`grant_type=password`, `client_id=acled`) → access (24 h) + refresh (~14 d);
    read at `GET /api/acled/read` with `Authorization: Bearer`, filter
    `event_date={start}|{end}&event_date_where=BETWEEN`, paginated `?page=N`
    (500/page). Tokens cached in `cache/acled/_token.json` (**never** in
    secrets.toml). Live: 256 events (Jun-2024 wk), 907 (Jan-2023).
  - **ACLED admin1 strings confirmed live** (≠ the hyphen guesses): `Deir ez Zor`,
    `Ar Raqqa`, `Al Hasakeh`, `Lattakia` — pinned in `acled.ACLED_ADMIN1` for S10.
  - **HDX** — public CKAN `package_search`, **no key**; live (returns
    `hdx-hapi-food-security`, `acaps_syria_core_dataset`, …).
  - **ReliefWeb** — **v1 decommissioned (HTTP 410); v2 requires a pre-approved
    `appname`** restricted to organizations listed with ReliefWeb (HTTP 403
    otherwise). **Superseded by DEC-022** — ReliefWeb is dropped for GDELT.

- **DEC-022** (S5/W3) — **ReliefWeb dropped; replaced by GDELT for news
  corroboration.** ReliefWeb's API is gated to organizations *listed with
  ReliefWeb* (DEC-021), so it is removed. `clients/hdx.py` keeps HDX and gains
  `search_gdelt()` over the GDELT DOC 2.0 news API (`api.gdeltproject.org`,
  **no key, no listing**), queryable by keyword + `sourcecountry:` + date window,
  cached per query (§9).
  - *Why GDELT:* it is the closest no-auth equivalent for the role ReliefWeb
    served — narrative/news corroboration of the flood and fire event windows
    (dossier §4.4) — and removes the credential/registration barrier entirely.
    HDX (datasets) plus the already-catalogued GIEWS/FEWS NET/IPC (S8) cover the
    food-security narrative; GDELT restores the dedicated news-search angle.
  - *Caveats carried in code:* GDELT's public endpoint allows **≤1 request / 5 s**
    — the client throttles uncached calls and retries a 429 with escalating
    backoff (4 attempts); the cache means re-runs never re-spend the budget. Like
    ACLED, GDELT has **no articles for a window ahead of real-world time** (the
    simulated 2026 date), so a 2026-window query returns empty until that date
    actually arrives — a data-availability property, not a client bug.
  - *Verification status:* the client is unit-test-proven (cache hit/miss,
    no-re-pull, 429-backoff retry, date-span formatting — `clients/test_clients.py`,
    23 tests). A **live 200 payload could not be obtained from this environment's
    egress IP** (GDELT rate-limited it beyond the documented 5 s after the probe
    burst); the endpoint is confirmed reachable (its own 429 body) and the request
    shape matches the API. Re-verify the live pull from an un-throttled IP at S8.
  - *Recommended §5 / §7 edit (flagged, not silently applied — per Working Rules,
    as with [[DEC-013]]):* `docs/STRUCTURE.md` §5 row "HDX / ReliefWeb" and §7 W3
    "HDX/ReliefWeb" should read **"HDX / GDELT"**. Left to the human.
  - *Downstream:* S8 (food-security context) uses `search_hdx` + `search_gdelt`;
    no ReliefWeb config remains (`[reliefweb]` removed from README/secrets).

> **Numbering note (S7, parallel with S6).** S6 (floods/W4) and S7 (fires/W5) ran
> concurrently from the same DEC-022 baseline. To avoid a numbering collision
> without live coordination, **S7/fires reserved the block DEC-030+**, leaving
> **DEC-023–029 for S6/floods**. The two sessions both append here, so a git merge
> will textually conflict at end-of-file — resolve by keeping both blocks (the
> number ranges are disjoint, so no renumber is needed). If S6 used >7 decisions
> and reached DEC-030, renumber the *floods* overflow, not these.

- **DEC-030** (S7/W5) — **FIRMS area-API per-request day-range cap corrected from
  10 to 5** in `clients/firms.py` (`_MAX_DAY_RANGE = 5`). The live API now rejects
  `day_range > 5` with HTTP 400 `"Invalid day range. Expects [1..5]."` — it
  accepted 10 when S5 built the client (2026-06-12). Window chunking and the
  per-chunk caching are otherwise unchanged; a multi-day request still costs
  `day_range` rate-limit transactions ([[DEC-021]]).
  - *Why:* upstream contract change — the client must match the live cap or every
    pull > 5 days fails. Common-sense correctness over the stale literal.
  - *Downstream:* affects every FIRMS caller (S7 here; S10/RQ2 later). Cache keys
    include the chunk size, so re-running after this change re-pulls in 5-day units
    (the old 10-day cache units, if any, are simply not hit — no corruption).
  - *Flagged for S5/merge:* this is a one-line fix in a client S5 owns; S6/floods
    does not touch `firms.py`, so no cross-session conflict is expected.

- **DEC-031** (S7/W5) — **A Sentinel-2 dNBR burn scar is counted as fire damage
  ONLY where it lies within 375 m of a VIIRS active-fire detection** (the
  "near-fire" confirmation, `active_fire.near_fire_mask`, 375 m = one VIIRS pixel).
  Burned-cropland hectares = `dNBR-severity ∩ near-fire ∩ cropland`.
  - *Why:* over cropland, dNBR drops sharply at **harvest and ploughing** too
    (green crop → bare soil), which would inflate "burned" area with ordinary
    agricultural turnover. Requiring co-location with an independent active-fire
    detection (VIIRS, the §6/DEC-006 primary sensor) discriminates *fire* from
    *harvest* — the discriminator PAX's Sentinel-2 method relies on. Severity
    thresholds themselves are unchanged ([[DEC-009]] Key & Benson bins).
  - *Trade-off (documented, for the human gate):* this is **conservative** — a
    genuine cropland burn that VIIRS missed (small/brief/cloud-gap overpass) is not
    counted, so the estimate is a **lower bound** on burned cropland. The Tier-2
    human review (vs EMSR811) judges whether the confirmation is too strict.
  - *Downstream:* W5 records; the same guard is the template for any fire-scar work
    (S10/RQ2). Revisit the 375 m buffer here if review finds it clips real scars.

- **DEC-032** (S7/W5) — **Fire DamageRecords carry the UNION-cropland hectares as
  the in-schema headline; the union-vs-intersection range lives in a companion
  sensitivity table.** Per [[DEC-015]] damage is reported under both cropland
  definitions, but the shared schema (§3.2) has one `damaged_cropland_ha` per
  `(aoi, date, severity)` key. So `outputs/tables/fire_damage.{csv,parquet}` =
  union headline (`source_layer="S2_dNBR"`, all `unvalidated`);
  `outputs/tables/fire_damage_sensitivity.csv` = `ha_union, ha_intersection` per
  key. The **2025 Latakia EMSR811** event is processed as a **method-validation
  anchor only** (`fire_validation_anchor_emsr811.csv`) — pre-2026 is
  baseline/context ([[DEC-001]]), never a study damage record.
  - *Why union headline:* [[DEC-015]] pins union as the headline so cropland
    extent (hence damage) is not silently under-counted; intersection is the
    conservative bound. Keeping intersection in a side table avoids two schema rows
    per key (which would risk a downstream **double-count** in S8 food-security).
  - *Why a side table, not source_layer encoding:* overloading `source_layer` with
    a `_union`/`_intersection` suffix would force every downstream consumer to know
    the convention or double-count; one clean headline + an explicit sensitivity
    file is safer.
  - *Flagged for S6/S8 alignment:* S6/floods faces the identical union/intersection
    question ([[DEC-015]] applies to both pipelines). **Recommend S6 adopt the same
    convention** (union headline in the schema, range in a sensitivity table) so the
    food-security layer (S8) reads one consistent headline column across phenomena.
  - *Headline result (UNVALIDATED, pending Tier-2):* Hasakah 2026 = **3,757.7 ha**
    burned cropland (union; 2,942.9 ha intersection); Latakia 2026 ≈ **1.1 ha**
    (2026 season barely begun, the July peak is in the simulated future). EMSR811
    anchor (2025, forest) = 17 ha *cropland* only — correct, that wildfire burned
    coastal forest, not cropland; the method check is the *full* scar vs EMSR811.
