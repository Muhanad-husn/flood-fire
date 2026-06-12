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
