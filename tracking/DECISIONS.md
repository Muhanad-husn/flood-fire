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
