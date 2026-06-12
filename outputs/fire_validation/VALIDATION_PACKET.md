# Pipeline B (Fires) — Tier-2 Validation Packet (W5 / Session 7)

> **STATUS: UNVALIDATED — awaiting human review.**
> Every fire `damaged_cropland_ha` record is **Tier-2 human-gated** (`docs/STRUCTURE.md` §6,
> DEC-007). Tests passing and agent convergence are **not** correctness here. The
> food-security layer (S8) and RQ analyses will **refuse** to consume any record whose
> `validation_status != validated`. **Only a human may flip `validation_status`** — no
> agent or Workflow run.

## What was produced

| Artifact | Path | Note |
|---|---|---|
| Study damage records (UNION headline) | `outputs/tables/fire_damage.csv` / `.parquet` | 8 records, all `unvalidated` |
| Union vs intersection sensitivity | `outputs/tables/fire_damage_sensitivity.csv` | DEC-015 range + EMSR811 anchor rows |
| EMSR811 method-validation anchor | `outputs/tables/fire_validation_anchor_emsr811.csv` | 2025 Latakia (context only, DEC-001) |
| Raw VIIRS hotspots | `outputs/fire_hotspots/*_viirs.csv` | provenance |
| Validation figures | `outputs/fire_validation/*_validation.png` | context + zoom panels |

## Headline numbers (UNVALIDATED)

| AOI | Window | Hotspots | Burned cropland — **union** | intersection |
|---|---|---|---|---|
| **Hasakah** | 2026-05-01 → 06-12 | 1925 | **3,757.7 ha** (low 1335 · mod-low 1569 · mod-high 769 · high 84) | 2,942.9 ha |
| **Latakia** | 2026-05-01 → 06-12 | 9 | **1.1 ha** | ~0 |
| _Latakia (anchor)_ | _2025-07-01 → 07-20_ | _915_ | _17.0 ha cropland (forest fire — see below)_ | _8.4 ha_ |

## Method (what the human is validating)

1. **Detection** — FIRMS **VIIRS 375 m** active-fire hotspots (never MODIS; DEC-006), cached.
2. **Severity** — Sentinel-2 **dNBR = NBR_pre − NBR_post** on cloud-masked median composites,
   classified into the pinned Key & Benson bins (DEC-009): `<0.10 unburned · 0.10 low ·
   0.27 moderate_low · 0.44 moderate_high · 0.66 high`.
3. **Fire confirmation (DEC-031)** — a dNBR scar is counted as fire damage **only within 375 m
   of a VIIRS hotspot**. This discriminates *fire* from *harvest/ploughing*, which also drop NBR.
   → The estimate is therefore a **conservative lower bound** (a real burn VIIRS missed is not counted).
4. **Cropland** — intersected with the canonical DEC-015 definition (cross-checked to match the
   human-reviewed `aois/cropland_mask.tif` within 0.5% on Hasakah). Reported under **union**
   (headline) and **intersection** (conservative).

## How to validate (the human gate)

**For the 2026 study AOIs (Hasakah, Latakia):**
- Open `hasakah_2026_validation.png` / `latakia_2026_validation.png`.
- **Left panel** = all VIIRS hotspots over post-fire S2 true-colour. **Right panel** = zoom on the
  densest cluster with the dNBR severity scar.
- Judge: do the severity scars **co-locate with hotspots** and sit on plausible cropland? Do they
  look like burns rather than artefacts (cloud edges, water, harvest blocks)?
- Cross-reference the hotspot CSVs if needed (`outputs/fire_hotspots/`).

**For the EMSR811 anchor (the named ground truth, §6):**
- **Download** the Copernicus EMS **EMSR811** delineation (Latakia, July 2025) from the
  [Copernicus EMS Rapid Mapping portal](https://emergency.copernicus.eu/) (vector / grading product).
- Overlay it on `latakia_2025_emsr811_validation.png` (the scar there is shown **full**, not
  cropland-confined, because EMSR811 burned **coastal forest, not cropland** — hence only ~17 ha
  of *cropland* burned, which is the correct, expected result).
- Judge: does our dNBR-confirmed scar **reproduce the EMSR811 burn footprint**? This validates the
  *method*; PAX's Sentinel-2 methodology is the named precedent.

## Recording the verdict

For each study record in `fire_damage.csv`, set `validation_status` to `validated` or `rejected`
(human edit only). If the method is judged sound against EMSR811 but a specific AOI/severity looks
wrong, reject that record and note why. **Downstream (S8) consumes only `validated` records.**

## Caveats / known limits (carry to the human)

- **July 2026 is in the simulated future** (today = 2026-06-13; VIIRS NRT ends 2026-06-12). The
  May–July fire season is covered only through **June 12**; the **Latakia 2026 signal (9 hotspots)
  is near-zero because its peak season (July+) has not occurred** — not because there were no fires.
- DEC-031 confirmation makes the estimate a **lower bound**; revisit the 375 m buffer if review
  finds it clips real scars.
- A single pre/post dNBR pair approximates a season of staggered fires (cumulative scar). Adequate
  for stubble-burn scars; flag if it misreads multi-burn pixels.
