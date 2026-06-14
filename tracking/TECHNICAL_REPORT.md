# Syria 2026 Agricultural Shocks — Technical Report on Work Completed

**Status as of 2026-06-15** · Branch `main`, clean · 85 tests passing · Report published to GitHub Pages · Verification pass complete (15 PASS / 0 FAIL / 1 GAP)

> One-line framing: A two-pipeline (floods + fires) remote-sensing study quantifying how 2026 water-and-fire shocks dented Syria's tentative cereal recovery, measured against the 2025 record-drought baseline — carried from a scaffolded repo to a published, peer-reviewed, reproducible report. Every damage number is human-validated; every headline is framed as a **first-half-2026 lower bound**.

This document follows the project's actual life cycle (left-to-right along the data flow), citing decisions from `tracking/DECISIONS.md` as `DEC-0xx`.

---

## 0. How to read this

The project's spine is the **shared damage schema** — both pipelines emit the *same* output, `damaged_cropland_ha` per AOI per date, which is what makes floods and fires one study rather than two. The lifecycle moves: contracts → foundation → inputs → the two parallel pipelines → integration → the three research questions → verification → presentation.

---

## 1. Planning & contract phase (DEC-001 → DEC-008)

Seven locked decisions everything downstream obeys:

| Locked decision | What it fixes |
|---|---|
| DEC-001 | Scope = **2026 events only**; all pre-2026 data is baseline/context, never a study record |
| DEC-002 | Two phenomena → two parallel pipelines → **one repo, one shared damage schema** |
| DEC-003 | **No** deep-learning/CV; **no** earthquake analysis |
| DEC-004 | Primary question = **food-security impact vs the 2025 drought baseline** |
| DEC-005 | RQ1 flood attribution, RQ2 fire attribution, RQ3 **descriptive** control overlay (never causal/differential) |
| DEC-006 | **Sentinel-1 SAR** = primary flood sensor; **FIRMS VIIRS 375 m** = primary fire sensor |
| DEC-007 | **Human-in-the-loop validation mandatory** for every Tier-2 output; agents cannot self-certify |

**DEC-008** set the presentation target: a **static, reproducible Quarto report** to GitHub Pages — Streamlit and any running-server dashboard explicitly rejected, because the project is portfolio/publication output, not an operational tool, and reproducibility is a first-class success criterion.

---

## 2. Foundation — W0 / Session 1–2 (DEC-009 → DEC-013)

**Schema finalized** (`schema/damage_schema.py`):
- **DEC-009** — `severity_class` per phenomenon: floods = `transient | persistent | permanent_excluded`; fires = `unburned | low | moderate_low | moderate_high | high` (Key & Benson / USGS dNBR bins). Non-damage classes carry `0.0` ha so exclusions are explicit.
- **DEC-010** — canonical `outputs/` format = **CSV (interchange) + Parquet (typed)**, lossless round-trip. Schema core imports **no geo/pandas deps** (pandas lazy-imported only in Parquet helpers).

**GEE auth wired** (`clients/gee_auth.py`):
- **DEC-011** — billing project from `EE_PROJECT`; idempotent; never launches interactive auth in a retry loop.
- **DEC-012** — added a **service-account key** path because Google blocks the `drive` OAuth scope for the default EE client ID. Verified live against `rich-stratum-429021-u4`.
- **DEC-013** — CHIRPS daily ID drift caught: spec's `UCSB/CHG/CHIRPS/DAILY` does not resolve; corrected to `UCSB-CHG/CHIRPS/DAILY`. Flagged, not silently edited. Other 8 GEE IDs verified.

---

## 3. Shared spatial assets — W1 / Session 3 (DEC-014 → DEC-016)

- **DEC-014** — Canonical AOIs from **FAO GAUL 2015 level-1** (GEE-native, reproducible). Originally 4 study AOIs; `aoi_id` strings are the stable schema keys.
- **DEC-015** — **Cropland mask** = one categorical 30 m raster (`aois/cropland_mask.tif`, EPSG:32637), union-first with disagreement encoded in-band: `1`=WorldCover-only, `2`=DynamicWorld-only, `3`=both. **Cropland = {1,2,3} (union headline); {3} = intersection (conservative).** Every damage number is therefore a **union-vs-intersection sensitivity range**.
- **DEC-016** — large rasters via **`geedim` tiled getPixels + mosaic** (Drive scope blocked, DEC-012).

The mask passed a **Tier-2 human review gate** (commit `5b097b6`) before any pipeline consumed it.

---

## 4. The 2025 drought baseline — W2 / Session 4 (DEC-017 → DEC-019)

The contrast the whole study rests on: drought is the trajectory, the 2026 shocks the anomaly against it.

- **DEC-017** — **CHIRPS rainfall deficit** (Nov 2024–May 2025 vs 1991–2020 normal): Deir ez-Zor −26.1%, Raqqa −19.8%, Hasakah −25.3%, Latakia −23.0%.
- **DEC-018** — **2025 NDVI anomaly** (S2 Mar–May max NDVI vs 2019–2024 mean, on cropland): **87.6% of cropland pixels negative**; inland-to-coast gradient tracks the deficit. Valid cropland = 2,388,480 ha, pixel-perfect to the S3 union total.
- **DEC-019** — **2025 cereal floor** (~1.2 Mt FAO/GIEWS) disaggregated across all 14 governorates by cropland-area share, summing exactly to the floor. Documented uniform-yield assumption.

---

## 5. Data-access clients — W3 / Session 5 (DEC-020 → DEC-022)

`clients/` — all four sources on **one shared cache + config layer** (`clients/_common.py`):
- **DEC-020** — gitignored `secrets/secrets.toml` (env override); per-request-unit cache is the checkpoint — `Cache.cached()` hits without calling fetch, so retries never re-pull. 22+ Tier-1 tests.
- **DEC-021** — live access models pinned (FIRMS VIIRS 375 m only; ACLED OAuth2; HDX CKAN). Surfaced the constraint that later shaped RQ2: **NRT ~2 months; ACLED lags ~1 year.**
- **DEC-022** — **ReliefWeb dropped** (gated to listed orgs) → **GDELT** for news corroboration (no key/listing).

---

## 6. Pipeline A — Floods → validated damage — W4 / Session 6 (DEC-023 → DEC-024)

`pipelines/floods/`. DEC-006: Sentinel-1 SAR.

- **DEC-023** — flood extent = S1 change-detection vs an **in-season per-relative-orbit median**, gated to floodplain (MERIT Hydro HAND < 15 m), dual-pol open-water (VV < −18 dB AND VH < −24 dB), minus JRC permanent water. **Two false-positive modes found and fixed**: a dry-summer reference flagged spring crop canopy as flood (~10⁵ ha); a single-band rule admitted bare harvested fields. Fixes isolate a coherent late-May/June Euphrates surge.
- **DEC-024** — event dates auto-selected from the S1 revisit series (5 wettest); severity = cross-date persistence; union/intersection in `source_layer`.

**Tier-2 gate closed** (`fec6e59`): **all 63 flood records human-validated.** Limitation: SAR captures open standing water; flooded vegetation and pluvial upland flooding under-detected → a lower bound.

---

## 7. Pipeline B — Fires → validated damage — W5 / Session 7, re-scoped at S13 (DEC-030 → DEC-032, DEC-037 → DEC-039)

`pipelines/fires/`. DEC-006: FIRMS VIIRS 375 m + Sentinel-2 dNBR.

- **DEC-031** — a dNBR scar counts as fire damage **only within 375 m of a VIIRS active-fire detection** — discriminates *fire* from *harvest/ploughing* (both drop dNBR). Conservative → a lower bound.
- **DEC-032** — fire records carry **union hectares as the in-schema headline**, intersection in a sidecar table (avoids a downstream double-count).

**The major mid-project correction (DEC-037, S13).** Spec named Hasakah + Latakia for fires, Latakia anchored on the **2025 EMSR811 forest fire** — wrong year *and* wrong land cover for a 2026 cropland study. A national 2026 VIIRS scan showed Latakia = 9 hotspots, **0 on cropland**, while 2026 crop fire is **national and Hasakah-dominant**. User-authorized re-scope **2→14 governorates** (first 4 `aoi_id`s kept byte-stable). Method unchanged; AOI loop widened.

- **DEC-038** — Latakia and Damascus City **verified-excluded** by running the full method (Latakia 1.05 ha union; Damascus City 4.47). Documented as *assessed negligible*, not silently dropped.

**Result:** **48 national study records across 12 governorates, ~10,533 ha union / ~6,600 ha intersection** (Hasakah dominant, 4,124 ha). **Tier-2 gate closed** — all 48 validated, superseding the old 8-record set.

- **DEC-039** (study-wide caveat) — a **first-half-2026 case study**. Fire window May 1–Jun 12; the Jun–Aug peak is **not yet observed**. **Every headline is a lower bound**; the conclusive result needs a **post-harvest re-run** plus field/expert verification.

---

## 8. Integration — Food-security impact layer — W6 / Session 8, re-run at DEC-040 (DEC-033, DEC-040)

`food_security/impact_layer.py`. The §3.4 chain: validated `damaged_cropland_ha` → production loss → indicative food-security pressure vs the 2025 baseline.

- **DEC-033** — resolves four traps:
  1. **Validation gate** — `gate_records(strict=True)` *refuses* (raises) on any non-validated record; reads the schema only, never rasters.
  2. **Cross-pipeline normalization** — floods (two-row encoding) and fires (union-headline + sidecar) normalized onto **one union headline** on read. No flood double-count.
  3. **Flood temporal double-count avoidance** — a `persistent` pixel recurs on every flood date, so headline flood-affected cropland = the **peak single event-date extent** (conservative snapshot).
  4. **Conservative yield** — loss = ha × the 2025 **drought-floor** yield (~0.223 t/ha), a deliberate lower bound (2026 was a recovery year).
  - Output is an **indicative qualitative band**, explicitly **not** an IPC phase — a production shock *feeding* GIEWS/FEWS NET/IPC.
- **DEC-040** — re-run after the S13 national re-scope; study area widened 4→**12 governorates**. A previously *silent* `b is None` skip (dropping 9 new fire-only govs) now emits a `UserWarning`.

**Final validated headline** (`outputs/food_security/impact_national.csv`):

| Metric | Value |
|---|---|
| Study-area cereal-production loss (headline) | **25,925 t** |
| Range (low – season-ref) | **3,471 – 39,946 t** |
| As % of the 12 study govs' 2025 baseline (~1.199 Mt ≈ national floor) | **2.16%** |
| Dominant contributors | Raqqa 10,253 t (7.8%) · Hasakah 9,562 t (2.8%) · Deir ez-Zor 4,997 t (7.6%) — flood-driven |
| 9 new fire-only govs combined | ~1,114 t (each *marginal*) |

Floods dominate the tonnage; the enlarged national fire footprint (~10,533 ha) adds modest tonnage because most new-gov fires are small at the conservative drought-floor yield.

---

## 9. The three research questions — W7–W9 / Sessions 9–11 (DEC-034 → DEC-036, DEC-041)

All three are *reasoning* layers (no `damaged_cropland_ha` output → no Tier-2 gate); each consumes validated records read-only.

**RQ1 — Flood attribution (DEC-034, DEC-035).** Added a **GloFAS discharge** client (`cems-glofas-historical` `intermediate` product via Copernicus EWDS). Per-event mechanism by river geography + rainfall/discharge coincidence. Finding: **Euphrates AOIs = upstream/transboundary-sourced, high confidence** — June flooding coincides with a sustained ~1,600 m³/s dry-season plateau (~6× drought baseline) at **zero local rainfall**. Natural-vs-managed-release = **LOW confidence; no dam-release fraction asserted**. **Flag surfaced, not resolved:** the **Hasakah-June** validated flood records have *no water source* (Khabur below baseline, zero rain) — the DEC-023 SAR harvest-artifact mode; RQ1 declines to attribute them.

**RQ2 — Fire attribution (DEC-036).** Built a defensible **cropland-restricted spatial null** (a raw "% near conflict" is indefensible — fires and conflict co-locate by geography). **Constraint:** live ACLED Syria ends 2025-06-13, so the **2026 overlay cannot be computed** — a *data-availability gap*, demonstrated on the analogous 2025 window: crop fires **no closer to armed conflict than cropland in general** → agricultural/seasonal. (Reinforced by the user's expert assessment: **no active armed conflict** in the 2026 window — fires are a **drought-and-heat hazard**.)

**RQ3 — Descriptive control overlay (DEC-041).** Strictly descriptive (DEC-005): maps *where* validated damage falls relative to indicative government / former-AANES zones, **never** stating either administration fared better. Held to the 4 AOIs where control geometry exists; Deir ez-Zor reported **unapportioned** (apportioning would require reading forbidden rasters). Every artifact carries the INDICATIVE/CONTESTED caveat.

---

## 10. Verification & reproducibility — W10 / Session 12 (DEC-042)

`analysis/verify.py` + `tracking/VERIFICATION_REPORT.md` — a reproducible, test-guarded audit:
- **Schema conformance** — all 63 flood + 48 fire records validate.
- **Validation-gate integrity** — every consumed record is human-`validated`; `gate_records(strict)` refuses otherwise; **no code path can confer `validated`**.
- **Reproducibility** — the deterministic schema→food-security→RQ3 chain recomputes from committed CSVs; CSV↔Parquet round-trips losslessly; pulls cached/checkpointed.

**Result: 15 PASS · 0 FAIL · 1 GAP.** The single GAP is RQ2's ACLED-2026 data-availability gap (not a defect). Known gaps recorded honestly: Hasakah-June flood flag, case-study scope, union/intersection spread. **Verdict:** meets its definition of done **as a first-half-2026 case study with lower-bound figures**, pending the post-harvest re-run. **85 tests pass.**

---

## 11. Presentation — Quarto report → Pages → peer review (DEC-008, DEC-043)

- **Build** (`5bf1fbc`) — Quarto report from validated outputs only (`freeze: auto` so rendering never re-triggers GEE pulls; figures consume only consumable records).
- **Publish** (`e78b9c5`) — GitHub Pages via Actions (later bumped to Node-24 majors).
- **Peer-review pass (DEC-043, `9588a72`)** — restructured **findings-first** for a humanitarian/policy/journalist reader, methods rigor preserved underneath. Added a governorate loss-% **choropleth** (drawn pure-matplotlib to keep CI geo-stack-free — a DEC-008 deviation surfaced and justified). Added a robustness figure: headline is **robust** to the Hasakah-June flag (25,925 t → 24,536 t, a 5.4% move). Added a one-page executive brief, an RQ index, confidence pills, a glossary. **No caveat softened, no headline number changed.**
- Latest commit (`4a78a1a`) wired validation photos to upload alongside the report.

---

## 12. Where the project stands

**Done and verified:** the full pipeline from raw GEE/API pulls to a published, peer-reviewed report. Both Tier-2 gates closed (63 floods, 48 fires, all human-validated). Food-security integration, all three RQs, and a reproducibility audit complete. 85 tests green.

**Honest open items (all surfaced, none hidden):**
1. **Post-harvest re-run** (DEC-039) — recommended next milestone (≈ after Jul–Aug 2026); current figures are H1-2026 lower bounds.
2. **RQ2 ACLED-2026** (DEC-036/042) — completes automatically, no code change, once ACLED ingests 2026 Syria events.
3. **Hasakah-June flood flag** (DEC-035) — revisit via an independent flood product at the re-run (headline robust to it).
4. **Field/expert verification** (DEC-039) — the gold standard above remote-sensing self-consistency.

**The one number to remember:** ~**26 kt** of additional 2026 cereal loss (range 3.5–40 kt), **~2.2% on top of** an already record-drought ~1.2 Mt national floor — flood-dominated, fire-broadened, and explicitly a **first-half-2026 lower bound**.
