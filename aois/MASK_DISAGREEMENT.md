# Cropland-mask disagreement note (W1 / S3)

Required by `docs/STRUCTURE.md` §3.1 and §9 ("document cropland-mask disagreement,
Dynamic World vs WorldCover"). Companion to `cropland_mask.tif`; numbers from
`outputs/aoi_qc/summary.json` (in-polygon, 30 m, EPSG:32637, 0.09 ha/pixel).

## What the mask encodes

`cropland_mask.tif` is one categorical raster (DEC-015):

| value | meaning | counts as cropland? |
|---|---|---|
| 0 | neither source | no |
| 1 | **WorldCover only** | yes (union) — a disagreement pixel |
| 2 | **Dynamic World only** | yes (union) — a disagreement pixel |
| 3 | **both agree** | yes (union **and** intersection) |
| 255 | outside AOI | nodata |

- **UNION** (headline) = values {1,2,3}. **INTERSECTION** (conservative) = value 3.
- Sources: ESA WorldCover v200 (class 40); Dynamic World annual-mean `crops`
  probability > 0.35 over 2021 (the WorldCover reference year).

## Cropland by AOI — union vs intersection

| AOI | union ha | intersection ha | WC-only ha | DW-only ha | disagreement* |
|---|--:|--:|--:|--:|--:|
| Deir ez-Zor | 287,642 | 81,154 | 202,352 | 4,137 | **72%** |
| Raqqa | 576,776 | 209,898 | 348,917 | 17,962 | **64%** |
| Hasakah | 1,513,953 | 846,302 | 649,694 | 17,957 | **44%** |
| Latakia | 9,876 | 2,791 | 4,385 | 2,700 | **72%** |
| **total** | **2,388,247** | **1,140,145** | **1,205,348** | **42,756** | **52%** |

\* disagreement share = 1 − intersection/union (fraction of union-cropland on which
the two sources disagree).

## The systematic pattern

**WorldCover is far more liberal than Dynamic World.** Across every AOI the
disagreement is overwhelmingly *WorldCover-only* (1.21 M ha) versus *Dynamic
World-only* (0.04 M ha) — a ~28:1 ratio. WorldCover labels ~2–3× more land as
cropland than the DW `crops > 0.35` rule. Spatially (see `outputs/aoi_qc/`):

- **Agreement (class 3)** concentrates in the productive, irrigated/high-rainfall
  cores: the northern Hasakah/Jazira wheat belt, the Khabur valley, and the
  Euphrates/Balikh corridors in Raqqa and Deir ez-Zor.
- **WorldCover-only (class 1)** rings those cores — marginal **rainfed/fallow**
  land that WorldCover calls cropland but whose annual-mean DW crop probability
  stays below 0.35 (it spends much of the year as bare soil/sparse vegetation).
  This is largest, proportionally, in arid Deir ez-Zor (72% disagreement).
- **Dynamic World-only (class 2)** is rare everywhere.

## Why this matters downstream (and how to use it)

`damaged_cropland_ha` scales directly with the cropland definition. Because union
exceeds intersection by ~2× overall (and ~3.5× in Deir ez-Zor), **the headline
hectare figures depend materially on the union-vs-intersection choice.** Guidance
for W4/W5/W6:

1. **Report damage under both bounds** — union (recall-favouring) and intersection
   (precision-favouring) — as a sensitivity range, never a single point estimate.
2. Treat **class 3 (agreement)** as the high-confidence cropland core; treat the
   WorldCover-only ring as lower-confidence, rainfed/marginal extent.
3. The `crops > 0.35` DW threshold is a **judgement call** (DEC-015) and the main
   lever on the spread. If the human review (S3 Tier-2 gate) finds the union over-
   or under-calls real agricultural extent — e.g. WorldCover sweeping in rangeland,
   or DW dropping genuine rainfed fields — revisit the threshold in DEC-015 (not in
   code) and rebuild.

## Caveats

- Reference year is **2021** (WorldCover v200), not 2026; this is a *cropland
  extent* mask, not an annual crop map. The 2026 drought/fallowing context is
  handled separately by the baseline (W2), not by re-defining the mask.
- 30 m resolution (export-constrained, DEC-016) can miss sub-30 m field strips;
  narrow riparian plots may be under-represented at the Euphrates margins.
