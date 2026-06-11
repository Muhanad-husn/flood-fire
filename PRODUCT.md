# PRODUCT — Syria 2026 Agricultural Shocks

> **Version:** 0.1 (planning seed)
> **Status:** Planning. Intended as an input to continued planning in Claude Code.
> **Companion docs:** `STRUCTURE.md` (architecture, contracts, validation), `syria-2026-agri-shocks-dossier.md` (full data-source catalog + caveats).

## 1. One line

A data-science study quantifying how the 2026 floods and crop fires reversed Syria's tentative cereal recovery, measured for food-security impact against the 2025 record-drought baseline.

## 2. Problem & context

The 2026 flooding matters because it is an *anomaly* on a desertification trajectory, not a recurring hazard. The baseline is drought; the shock is water. That contrast is the analytical spine.

- **2025 — record drought (baseline).** FAO/GIEWS put the cereal harvest near 1.2 Mt, ~60%+ below average and the worst conditions in roughly 60 years; ~16.3M people at food-security risk.
- **2026 — tentative recovery.** Harvest projected to rebound toward ~2.3 Mt on more even rainfall and added support, though sowing targets were not fully met.
- **2026 — the shock.** April floods and hailstorms hit the recovering wheat at its critical final growth stage; the late-May Euphrates surge followed (flows ~2,000 m³/s against 200–250 in drought years, with dam spillway gates opened for the first time in 30+ years), submerging thousands of hectares of farmland in Deir ez-Zor and Raqqa.

Full attribution and figures live in the companion dossier (verify against latest FAO/GIEWS and FEWS NET before publication).

## 3. Goals

1. Quantify damaged cropland (hectares) from both floods and fires across the 2026 event windows, per area of interest.
2. Translate that physical damage into production and food-security impact, measured against the 2025 drought baseline.
3. Answer three secondary questions: flood attribution, fire attribution, and differential impact by area of control.
4. Deliver reproducible, validated, defensible outputs suitable for analytical publication and portfolio use.

## 4. Non-goals (explicit exclusions)

- **No deep-learning / computer-vision pipeline.** No model training on FloodPlanet, Sen1Floods11, or Incidents1M.
- **No earthquake analysis.** Out of scope entirely.
- **Not a real-time operational early-warning system.** This is retrospective analytical research.
- **Pre-2026 data is baseline/context only**, never the subject of analysis.
- **Not a humanitarian-response tool.** Outputs inform analysis, not field operations.

## 5. Research questions (locked)

**Primary.** How much of the 2026 cereal recovery was reversed by the floods and fires, and where — measured as damaged cropland hectares translated into production and food-security impact, against the 2025 drought baseline?

**Secondary 1 — Flood attribution.** How much of the 2026 flood is rainfall-driven versus driven by upstream dam releases? Discriminated with CHIRPS rainfall and GloFAS discharge against reported Euphrates flows.

**Secondary 2 — Fire attribution.** Are the 2026 crop fires concentrated along conflict frontlines and linked to military activity, or do they track accidental/agricultural burning? Tested by overlaying FIRMS/VIIRS hotspots and Sentinel-2 burn scars on ACLED conflict events.

**Secondary 3 — Damage relative to area of control (descriptive).** Where does the 2026 cropland damage fall relative to indicative government-controlled and former AANES areas? A descriptive spatial overlay, not a causal comparison: it maps the distribution of damage against control zones without inferring that either administration fared better or worse. Boundaries are contested and treated as indicative only.

## 6. Success criteria (product-level definition of done)

- Damaged-cropland-hectare estimates per AOI per event window, for both phenomena, **each validated against named ground truth** (Copernicus EMS EMSR811 for fire; GloFAS and any EMSR flood activation for floods; PAX methodology as fire precedent) — not "the code ran."
- A food-security impact translation tied to the GIEWS / FEWS NET / IPC baseline.
- RQ1: a rainfall-versus-discharge decomposition with explicit confidence and caveats.
- RQ2: a fire–conflict overlay with proximity-to-frontline and timing analysis.
- RQ3: a descriptive overlay of 2026 damage against indicative control-area boundaries, with explicit caveats that boundaries are contested and no differential or causal claim is made.
- End-to-end reproducibility: pinned sources, documented GEE collection IDs, cached pulls, runnable from a clean checkout.

## 7. Intended use & audience

Analytical research and portfolio output for a conflict- and governance-literate audience, with possible NGO relevance. This implies rigor over speed: named sources, defensible attribution, and proportionate framing of contested claims.

## 8. Constraints

- **Stack:** Python + Google Earth Engine.
- **Operating mode:** non-autonomous Claude Code; the human validates all raster outputs (see `STRUCTURE.md` §6).
- **Cost-conscious:** prefer scoped, checkpointed runs; reserve parallel/Workflow execution for rubric-eligible mechanical work only.
- **Environment:** Windows via WSL2 or conda for the geospatial stack.

## 9. Sensitivity & ethics

This is a conflict zone with contested administrative control, and the dam-attribution question is politically charged. Keep causal claims proportionate to evidence, attribute sources, and avoid overclaiming. Control-area framing (RQ3) must not assert boundaries the data cannot defend.
