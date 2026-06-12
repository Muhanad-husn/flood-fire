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
