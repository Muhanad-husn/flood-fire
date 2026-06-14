# RQ3 — descriptive damage-vs-control overlay (W9, DEC-005)

> ⚠ **INDICATIVE / CONTESTED boundaries — descriptive overlay only (DEC-005). NOT an authoritative control map. No differential or causal claim may be drawn: this layer does not state or imply that either administration fared better or worse. The Euphrates is used as a schematic proxy line; control geography is the indicative 2017-2024 predominant pattern.**

> ⚠ **First-half-2026 case study (DEC-039).** Damage figures cover floods Mar–Jun and fires May 1 – Jun 12 only; they are lower bounds on the full year.

## What this is (and is not)
- **Is:** a descriptive tabulation of *where* validated 2026 cropland damage falls relative to indicative control zones, at the shared schema's per-AOI granularity.
- **Is not:** a comparison. Nothing here states or implies that damage was higher/lower, or response better/worse, under either indicative administration. The control geography is contested and indicative; the Euphrates split of Deir ez-Zor is a schematic proxy.

## Scope
- **In scope:** the four AOIs where indicative control zones are defined (`aois/control_areas.geojson`): Deir ez-Zor, Raqqa, Hasakah, Latakia.
- **Out of scope:** the national fire-only governorates (S13/DEC-037) — control geometry was never drawn there, and extending contested boundaries to force an overlay would itself breach DEC-005. Their damage is listed separately, with no zone assigned.
- **Deir ez-Zor spans two indicative zones** (former-AANES NE / government SW of the schematic Euphrates line). The per-AOI schema cannot apportion its hectares between them, and an RQ analysis may not read the flood/fire rasters to do so (cross-reference discipline). It is therefore reported as **spanning both, unapportioned** — deliberately, not as an omission.

## Descriptive tabulation — validated damaged cropland by indicative zone

| Indicative zone | AOIs | Flood ha | Fire ha | Total ha |
|---|---|---:|---:|---:|
| former_AANES (indicative) | hasakah, raqqa | 83,338 | 5,348 | 88,686 |
| spans former_AANES + government (indicative; unapportioned) | deir_ez_zor | 22,166 | 198 | 22,364 |

*Hectares are the union-cropland headline (DEC-015/DEC-032), flood figures the peak single event-date extent (no cross-date double-count, DEC-033). Listing side by side is descriptive co-location, not a comparison.*

## Outside indicative control-area coverage (no zone assigned)
- National fire-only governorates (aleppo, daraa, hama, homs, idlib, quneitra, rural_damascus, suwayda, tartus): **4,987 ha** validated burned cropland, located outside the drawn indicative control geography. Reported for transparency; **no control zone is attributed.**

## Caveats (every artifact carries these)
- INDICATIVE / CONTESTED boundaries — descriptive overlay only (DEC-005). NOT an authoritative control map. No differential or causal claim may be drawn: this layer does not state or imply that either administration fared better or worse. The Euphrates is used as a schematic proxy line; control geography is the indicative 2017-2024 predominant pattern.
- Damaged hectares inherit the pipeline caveats: flood extent is open-water riverine inundation (DEC-023); burned cropland is VIIRS-confirmed dNBR, a conservative lower bound (DEC-031).
- First-half-2026 scope: figures are lower bounds; the summer harvest/fire peak is unobserved (DEC-039).

## Outputs
- `damage_by_aoi_zone.csv` — per AOI × phenomenon headline ha + its indicative zone.
- `damage_by_indicative_zone.csv` — descriptive totals grouped by indicative zone.
- `outputs/figures/w9_rq3_control_overlay.png` — the descriptive overlay map.
