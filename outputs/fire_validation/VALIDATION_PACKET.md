# Fire validation packet — NATIONAL re-scope (S13, DEC-037)

**Tier-2 human gate (§6, DEC-007).** These records are `unvalidated`. A human must
review the burned-cropland estimates against known 2026 fire geography / any 2026
Copernicus EMS fire activation / imagery before any `validation_status` is set to
`validated`. No agent flips it.

> **This SUPERSEDES the old 2-AOI packet.** The previous fire run (Hasakah + Latakia,
> 8 validated records) was re-scoped to **national** after the fire AOIs were found to
> be anchored on the 2025 EMSR811 *forest* fire (Latakia: 9 hotspots, **0 on cropland**
> in 2026). Those earlier validations **do not carry over** — the national 48-record set
> needs a fresh gate.

## What changed
- **AOIs:** 2 → **12 governorates with 2026 cropland fire** (national). Latakia dropped.
- **Method:** UNCHANGED from S7 — S2 dNBR severity (DEC-009) ∩ VIIRS near-fire 375 m
  (DEC-031) ∩ DEC-015 cropland; union headline + intersection sensitivity (DEC-032).
- **Window:** 2026-05-01 … 2026-06-12 (available VIIRS NRT slice; the July harvest-fire
  peak is in the simulated future — smaller-governorate totals will grow).
- **Framing:** fire is its own **drought/heat agricultural hazard** (dry vegetation at
  harvest), not a conflict story — per the user's expert assessment there was no active
  armed conflict in the window (RQ2 → agricultural/accidental, DEC-036/037).

## Burned cropland by governorate (UNVALIDATED — for review)

| Governorate | VIIRS hotspots | union ha (headline) | intersection ha (low) |
|---|---:|---:|---:|
| Hasakah | 2077 | **4,123.5** | 3,194.1 |
| Raqqa | 94 | 1,224.5 | 922.4 |
| Aleppo | 171 | 990.6 | 500.2 |
| Idlib | 69 | 901.2 | 709.2 |
| Homs | 651 | 740.0 | 353.5 |
| Daraa | 62 | 721.5 | 237.7 |
| Rural Damascus | 215 | 524.4 | 240.3 |
| Hama | 193 | 446.6 | 193.1 |
| Quneitra | 31 | 339.7 | 79.2 |
| Tartus | 35 | 230.0 | 168.0 |
| Deir ez-Zor | 945 | 197.8 | 9.5 |
| Suwayda | 6 | 93.2 | 5.7 |
| **National** | | **≈10,533** | **≈6,613** |

Severity breakdown per governorate is in `outputs/tables/fire_damage_sensitivity.csv`;
the canonical records (union headline) are in `outputs/tables/fire_damage.csv`.

## What to look at (review guidance)
- **Hasakah dominates** (~4,124 ha union) — the core 2026 cropland-fire signal, as before.
- **Corroboration to sanity-check:** Idlib (901 ha) and Daraa (722 ha) match the user's
  2026 reporting of wheat/barley field fires; Aleppo (991 ha) and the nationwide field-fire
  reports align with the spread.
- **Cropland-discrimination working:** **Deir ez-Zor** has many hotspots (945) but only
  198 ha union / **9.5 ha intersection** — most DeZ fire is **off cropland** (oil/desert),
  correctly excluded by the cropland ∩ near-fire gates. Raqqa/Idlib are the opposite (few
  hotspots, large cropland scars).
- **union vs intersection** brackets the DEC-015 DW/WC cropland disagreement; truth lies
  between. Large gaps (DeZ, Suwayda, Quneitra) flag rainfed/fallow-edge uncertainty.

## Per-governorate panels
`outputs/fire_validation/<aoi>_2026_validation.png` — VIIRS hotspots over post-fire
Sentinel-2 true colour (context) + a dNBR-severity zoom on the densest cluster.
`latakia_2025_emsr811_validation.png` is the **method-validation anchor** (2025 forest
fire; overlay the Copernicus EMS EMSR811 delineation to confirm the dNBR method) — NOT a
study record.

## Closing the gate
Set `validation_status` per record in `outputs/tables/fire_damage.csv`
(`unvalidated` → `validated`, or `rejected` for any governorate that fails review).
Then S8 (food-security) re-runs on the validated national set.
