# aois/ — canonical AOIs + cropland mask (shared)

Per `docs/STRUCTURE.md` §3.1. Every module consumes these canonical assets; **no
module redefines AOIs**. Built in W1 (Session 3); see `tracking/DECISIONS.md`
DEC-014/015/016.

## Assets

### `governorates.geojson` — canonical AOI boundaries (EPSG:4326)
Four AOIs from **FAO GAUL 2015 level 1** (`ADM0_NAME == "Syrian Arab Republic"`).
Properties: `aoi_id`, `name`, `gaul_adm1`, `area_km2`, `pipelines`, `source`.

| `aoi_id` | name | pipelines | area km² |
|---|---|---|---|
| `deir_ez_zor` | Deir ez-Zor | floods | 27,307 |
| `raqqa` | Raqqa | floods | 17,906 |
| `hasakah` | Hasakah | floods, fires | 22,758 |
| `latakia` | Latakia | fires | 2,429 |

`aoi_id` is the stable key referenced by the shared damage schema's `aoi_id`
field (`schema/damage_schema.py`, §3.2).

### `cropland_mask.tif` — reconciled cropland (EPSG:32637 / UTM 37N, 30 m)
One categorical raster reconciling **Dynamic World** and **ESA WorldCover**, with
the source disagreement encoded **in-band** (§3.1 "with disagreement documented"):

| value | meaning |
|---|---|
| `0` | neither source = cropland (non-cropland) |
| `1` | WorldCover only (disagreement) |
| `2` | Dynamic World only (disagreement) |
| `3` | both agree = cropland (agreement) |
| `255` | outside AOI (nodata) |

**Cropland = value ∈ {1, 2, 3}** (UNION — headline). **value == 3** = the
INTERSECTION (conservative). Downstream damage should be reported under **both**
as a sensitivity range (DEC-015). Sources: WorldCover v200 class 40; Dynamic
World annual-mean `crops` probability > 0.35 over 2021. Per-AOI 10 m→30 m mode
downsample, clipped to each polygon, mosaicked. See `MASK_DISAGREEMENT.md`.

> **Tier-2 gate (§6, DEC-007):** the mask is **human-reviewed** against known
> agricultural extent before any pipeline (W4/W5) consumes it. QC previews +
> hectare/disagreement summary: `outputs/aoi_qc/`.

### `control_areas.geojson` — RQ3 INDICATIVE overlay only (EPSG:4326)
Indicative government-controlled vs former-AANES areas. **Indicative / contested
— descriptive overlay only, never a causal or differential claim** (DEC-005,
`docs/PRODUCT.md` §5/§9). Five features; Deir ez-Zor is split NE/SW by a
**schematic Euphrates proxy line**, the others carry a single indicative label
from the 2017–2024 control geography. Every feature carries an explicit `caveat`
and `indicative: true`. **Not an authoritative control map** — a dated source
should replace it before RQ3 (S11) if a finer overlay is needed.

## Generators (reproducible)
- `build_aois.py` — `governorates.geojson` + `cropland_mask.tif` (GEE via
  `clients.gee_auth`; large rasters via geedim tiled download, DEC-016).
- `build_control_areas.py` — `control_areas.geojson` (local; reads
  `governorates.geojson`).
- `qc_preview.py` — per-AOI mask previews + hectare/disagreement summary for the
  human review gate.

Run order: `build_aois.py` → `build_control_areas.py` → `qc_preview.py`.
