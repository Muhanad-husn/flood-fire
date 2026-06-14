# Geospatial & Satellite-Imagery Methods — How the Pipelines Work

Companion to `tracking/TECHNICAL_REPORT.md`. This document explains the geospatial
engineering: which satellites we read, how raw imagery becomes
`damaged_cropland_ha`, the coordinate/resolution discipline, and the platform
constraints that shaped the design. Decisions cited as `DEC-0xx`
(`tracking/DECISIONS.md`).

---

## 1. The two-tier platform model: compute on GEE, decide locally

Everything happens in one of two places, and the split is deliberate:

- **Google Earth Engine (server-side).** All petabyte-scale imagery (Sentinel-1/2,
  WorldCover, Dynamic World, JRC GSW, MERIT Hydro, GLO-30, CHIRPS) lives in the GEE
  catalog. We never download a scene. Instead we build a **lazy `ee.Image`
  computation graph** — filter → mask → arithmetic → threshold — that GEE evaluates
  only when we ask for a number (`reduceRegion().getInfo()`) or a bounded raster
  (`geedim`). The pipeline modules (`flood_mask.py`, `burn_severity.py`,
  `active_fire.py`) hold *only* these server-side builders — no I/O.
- **Local (rasterio / geopandas / numpy).** The **authoritative** hectares are
  computed on-machine against the human-reviewed `aois/cropland_mask.tif`, never a
  server-side proxy. Speckle cleanup, polygon clipping, mosaicking, and the
  validation packets are all local. This is what a human gates (DEC-007).

> Rule of thumb: GEE does the heavy raster algebra; the *trusted* numbers are
> recomputed locally against the committed, human-reviewed artifacts.

---

## 2. Coordinate systems & resolution — the honesty discipline

| Concern | Choice | Why |
|---|---|---|
| Vector AOIs (`governorates.geojson`) | **EPSG:4326 / CRS84** | GeoJSON-native, GEE-native, no reprojection to store admin polygons |
| Authoritative rasters (cropland mask, NDVI anomaly) | **EPSG:32637 (UTM 37N)** | **Metric** pixels — a 30 m pixel is exactly **0.09 ha**, so area sums are honest, not distorted by lat/long degrees |
| Pixel grid | 30 m | Balances riparian-cropland fidelity against export cost; Latakia at the zone's western edge is <0.1% area-distorted (acceptable, DEC-015) |

**Resampling rules — the band type dictates the reducer:**
- **Categorical** layers (cropland classes) → `reduceResolution(mode)` 10 m→30 m
  (DEC-015). Mode preserves the dominant class; averaging class integers is
  meaningless.
- **Continuous** layers (NDVI) → bilinear, then reproject (DEC-018).
- **Mask alignment** (cropland onto an NDVI grid) → nearest-neighbour, so a binary
  mask stays binary.

**The projection trap we hit (DEC-018, repeated in `burn_severity.severity_class_image`):**
a `.max()` composite or a constant image **has no fixed projection**, so
`reduceResolution` silently fails on it. Fix: either `reproject()` first, or build
the derived image by *summing threshold comparisons of an already-projected band*
(`dnbr.gte(lo).add(dnbr.gte(ml))…`) so the result **inherits dNBR's projection**.
This is why severity is built additively rather than from a lookup on a blank image.

---

## 3. The satellite & raster inputs (what each sensor is for)

| Source (GEE ID) | Sensor / type | Role in the study |
|---|---|---|
| `COPERNICUS/S1_GRD` | **Sentinel-1 C-band SAR** (VV+VH, IW GRD, dB) | **Flood extent** — load-bearing; sees water through cloud (DEC-006) |
| `COPERNICUS/S2_SR_HARMONIZED` | **Sentinel-2 optical** (B8 NIR, B12 SWIR) | **Fire severity** via dNBR |
| FIRMS **VIIRS 375 m** (`clients/firms.py`) | Active-fire thermal detection | Fire *confirmation* — never MODIS for detection (DEC-006) |
| `ESA/WorldCover/v200` (cls 40) | 10 m land cover | Cropland mask — liberal source |
| `GOOGLE/DYNAMICWORLD/V1` (`crops`>0.35) | 10 m near-real-time land cover | Cropland mask — conservative source |
| `JRC/GSW1_4/GlobalSurfaceWater` | Permanent-water occurrence | Subtract the permanent river (not damage) |
| `MERIT/Hydro/v1_0_1` (`hnd`) | Height-above-nearest-drainage (HAND) | Floodplain gate — rejects dry upland false positives |
| `COPERNICUS/DEM/GLO30` | 30 m DEM → slope | Reject radar-shadow false positives |
| `UCSB-CHG/CHIRPS/DAILY` | Gridded rainfall (~5.5 km) | Drought baseline + RQ1 pluvial check |
| GloFAS (`cems-glofas-historical`) | River discharge reanalysis | RQ1 riverine attribution |

---

## 4. Pipeline A — turning Sentinel-1 SAR into flooded cropland

SAR measures **backscatter** (radar energy returned). Smooth open water is
*specular* — it reflects energy away from the sensor, so water reads **dark** (very
negative dB). Floods therefore show as a **drop** in backscatter vs a no-flood
reference. The full chain (`flood_mask.flood_binary`):

1. **Build the reference (the no-flood backdrop).** `seasonal_ref` = the **median
   of all in-season acquisitions of the *same relative orbit*** as the event date.
   - *In-season* (Mar–Jun) removes **crop-phenology bias**: an early attempt used a
     dry-summer reference, which made dense *spring crop canopy* look like a change
     → "flood" across whole governorates (~10⁵ ha of false positives). The seasonal
     median is the honest backdrop.
   - *Per-relative-orbit* keeps the **incidence-angle geometry matched** (backscatter
     depends on look angle; mixing orbits injects geometry as if it were change).
2. **Speckle pre-filter.** SAR is grainy (coherent-imaging speckle); a 50 m
   `focal_mean` (UN-SPIDER-recommended) smooths it before thresholding.
3. **The flood test (dual-pol AND, not OR):**
   ```
   flood = (VV_drop ≥ 4 dB)  AND  (event VV < −18 dB)  AND  (event VH < −24 dB)
   ```
   Requiring *both* VV and VH to be open-water-dark (an **AND**) roughly halves false
   positives vs a single-band OR. The drop-vs-median catches *change*; the absolute
   thresholds enforce *it's actually water-dark*.
4. **Floodplain gate (HAND < 15 m).** The dominant residual false positive is
   **smooth dry harvested fields in June** — post-harvest bare soil is specular and
   radar-dark, mimicking water. River floods sit in low terrain near drainage;
   harvested uplands sit above it. HAND removes the uplands while keeping the real
   Euphrates/Khabur riverine flood. (Trade-off: pluvial *upland* flooding is then
   under-captured — documented in the validation packet.)
5. **Subtract permanent water** (JRC GSW occurrence > 50%) so the permanent river is
   never counted as damage → the `permanent_excluded` class (DEC-009).
6. **Drop steep slopes** (GLO-30 > 5°) — radar-shadow false positives.
7. **Local connected-component cleanup** — flood blobs < 8 px (≈0.7 ha) dropped
   after export (done locally, not server-side, to dodge EE projection limits on a
   composite).

**Documented physical limitation (carried into the Tier-2 packet):** change-detection
on a backscatter *drop* captures **open standing water** only. Flooded *vegetation*
can *raise* VV via double-bounce and is under-detected — which is exactly why
optical / Dynamic World is the **confirmatory** layer (DEC-006, §9). Hectares are an
open-water riverine lower bound.

### Orchestration economy (`cropland_flooded.py`)
- **Screen → export → emit.** Every S1 date is first **screened** cheaply at 150 m
  (`flooded_cropland_ha`) to find **event dates** that exceed a dry baseline
  (`max(median + 3·MAD, 1.5·median, 500 ha)`), capped at the **5 wettest** per AOI.
  Only those get the full **30 m export**. This keeps GEE compute scoped (DEC-024).
- **Severity = cross-date persistence.** A pixel flooded on ≥2 event dates is
  `persistent`; one date = `transient` (DEC-009/024).
- **Authoritative intersect is local.** Exported flood rasters are intersected with
  the committed `aois/cropland_mask.tif` (human-reviewed), not the server proxy.

---

## 5. Pipeline B — turning Sentinel-2 + VIIRS into burned cropland

Fire uses **optical** imagery because burn scars are a *spectral* signature, plus a
**thermal** detector to confirm it was fire (not harvest). Chain (`burn_severity.py`
+ `active_fire.py`):

1. **Cloud-mask the optical composites.** `_s2_nbr` drops Sentinel-2 SCL classes
   {3 shadow, 8 cloud-med, 9 cloud-high, 10 cirrus, 11 snow} and takes a **median**
   composite over the pre- and post-fire windows (median is cloud/outlier-robust).
2. **NBR → dNBR.** `NBR = (B8 − B12)/(B8 + B12)` (NIR vs SWIR — healthy vegetation is
   high-NIR/low-SWIR; burning flips that). `dNBR = NBR_pre − NBR_post`; a burn drops
   NBR, so **dNBR > 0** over scars.
3. **Severity bins** (DEC-009, Key & Benson / USGS FIREMON): thresholds
   `0.10 / 0.27 / 0.44 / 0.66` → low / moderate_low / moderate_high / high. Built by
   **summing threshold comparisons** so the class image inherits dNBR's projection
   (§2 trap).
4. **The fire-vs-harvest discriminator (DEC-031).** Over cropland, dNBR *also* drops
   at **harvest and ploughing** (green crop → bare soil) — indistinguishable from a
   small burn spectrally. So a scar counts as fire damage **only within 375 m of a
   VIIRS active-fire detection**. `active_fire.near_fire_mask` buffers every hotspot
   by 375 m (one VIIRS pixel = the detection's spatial uncertainty) using
   `FeatureCollection.distance()`, then:
   ```
   burned_cropland = dNBR_severity  ∩  near_fire(375 m)  ∩  cropland
   ```
   This is conservative (a VIIRS-missed burn isn't counted) → a lower bound, by design.
5. **Area by severity.** `burned_cropland_ha` multiplies `ee.Image.pixelArea()` by the
   masked severity image and `reduceRegion(sum().group(by severity))` → m², ÷1e4 → ha,
   per class. Reported under **both** union and intersection cropland (DEC-015/032).

VIIRS hotspots come through the cached `clients/firms.py` (VIIRS 375 m only — NRT for
the 2026 window, `*_SP` archive for the 2025 EMSR811 anchor). Points are materialised
as a GeoDataFrame (EPSG:4326) for plotting and as an `ee.FeatureCollection` for the
mask; the buffered union is also the `reduceRegion` region that bounds compute.

---

## 6. The cropland mask — reconciling two satellites into one artifact

Cropland is itself a remote-sensing product, and the two best 10 m sources disagree
(WorldCover is liberal on rainfed/fallow land; Dynamic World's `crops>0.35` is
conservative). Rather than pick one, `build_aois.cropland_categorical` encodes **both
and their disagreement in one categorical raster** (DEC-015):

```
0 = neither   1 = WorldCover-only   2 = DynamicWorld-only   3 = both agree   255 = outside AOI
cropland = {1,2,3} (UNION, headline)        intersection = {3} (conservative)
```

Every damage figure is therefore reported as a **union-vs-intersection range** — the
honest expression of cropland-definition uncertainty, with no extra schema field.
Built at native 10 m, `reduceResolution(mode)` to 30 m, reprojected to UTM 37N,
clipped per-AOI, mosaicked. The DW/WC spread is large in rainfed Deir ez-Zor (~72%
disagreement) — surfaced in `aois/MASK_DISAGREEMENT.md`.

---

## 7. Export & area mechanics — the GEE constraints that shaped the code

- **No `Export.image.toDrive`.** Google blocks the EE `drive` OAuth scope for this
  project's auth (DEC-012), so the standard export path is unavailable. We pull
  bounded rasters with **`geedim` tiled `getPixels` + mosaic** (DEC-016):
  `prepareForExport` → `toGeoTIFF(max_tile_dim=1500, max_requests=2, nodata=255)`.
- **Restricted Mode.** The noncommercial tier throttles compute mid-session; geedim
  must run at `max_requests=2` (not 16) or it trips 429 concurrency errors. A retry
  loop with escalating backoff absorbs transient "user memory limit exceeded".
- **`geedim` fills outside-polygon pixels with 0, not nodata.** So the *authoritative*
  polygon clip is enforced **locally** in `mosaic_from_tiles`: `rasterio.features`
  `geometry_mask` sets outside-AOI → 255 before the per-AOI tiles are merged. The
  server clip only bounds compute; the trusted boundary is applied on-machine.
- **Area is true pixel area, never pixel-count × nominal.** Every hectare uses
  `ee.Image.pixelArea()` (the actual projected m² of each pixel) → `reduceRegion(sum)`
  → ÷1e4. Grouped reducers (`.group()`) give per-severity hectares in one server call.
- **Everything is cached/checkpointed.** GEE pulls, FIRMS/CHIRPS/ACLED/GloFAS
  responses, and exported tiles all land in gitignored cache dirs, so a throttled or
  interrupted run **resumes without re-spending quota** and a clean checkout
  reproduces the numbers (DEC-020, §9).

---

## 8. Vector handling notes

- **GAUL `GeometryCollection` normalisation.** FAO GAUL occasionally returns a
  governorate (e.g. Homs) as a `GeometryCollection`, which lacks a `coordinates` key
  and breaks downstream consumers. `build_governorates` unions the member polygons
  via shapely into a clean `MultiPolygon`.
- **VIIRS points → masks.** Hotspots are buffered (`buffer(375)`) and unioned; because
  `reduceRegion` treats the region as a set, overlapping buffers never double-count
  area.
- **CHIRPS is read AOI-mean, not cropland-masked** (DEC-017): at ~5.5 km, a CHIRPS
  pixel is far larger than a field, so masking the rainfall grid to 30 m cropland
  would be meaningless — the AOI mean is the honest meteorological quantity.

---

## 9. Why this is defensible

Every geospatial choice trades toward **proportionate, lower-bound claims** over
maximal numbers:
- dual-pol AND + HAND gate → fewer flood false positives (open-water lower bound);
- 375 m VIIRS confirmation → fewer fire false positives (misses small burns → lower bound);
- union/intersection range on every figure → cropland uncertainty made explicit;
- authoritative numbers recomputed locally against a **human-reviewed** mask, behind a
  Tier-2 gate no agent can flip (DEC-007).

The result is a remote-sensing estimate whose every known failure mode is documented
in the validation packet rather than hidden — the project's credibility engine (§9).
