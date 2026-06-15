# Syria 2026 Agricultural Shocks

**Measuring, from satellites, how the 2026 floods and crop fires set back Syria's fragile cereal recovery — on top of a record 2025 drought.**

In 2025 Syria's rainfed cereal harvest collapsed under the worst drought on record (a national floor near **1.2 million tonnes**). 2026 brought a tentative recovery — and then two shocks hit it: a spring/early-summer **Euphrates flood surge** that inundated riverside cropland, and a wave of **agricultural field fires** across the country at harvest time. This study quantifies that damage, field by governorate, from open satellite data — and asks how much it cost a food system that was already on the edge.

> 📊 **Read the full report →** https://muhanad-husn.github.io/flood-fire/ &nbsp;·&nbsp; 📄 [One-page executive brief](https://muhanad-husn.github.io/flood-fire/brief.html)

`main` · 85 tests passing · every damage figure human-validated · published to GitHub Pages

---

## What we found

A **first-half-2026 snapshot** (the harvest/fire season peaks later, so these are **lower bounds**, not final figures):

| Result | Figure |
|---|---|
| **Flood-affected cropland** (peak extent, 3 Euphrates/Khabur governorates) | **~105,000 ha** |
| **Burned cropland** (national, 12 governorates, union headline) | **~10,500 ha** |
| **Additional cereal-production loss** (study area, headline) | **~25,900 t**  (range 3,500–40,000 t) |
| **…as a share of the ~1.2 Mt national 2025 floor** | **~2.2%**, on top of an already record-low harvest |
| Worst-hit governorates | **Raqqa −7.8%**, **Deir ez-Zor −7.6%**, **Hasakah −2.8%** of their 2025 baseline |

**The shape of the story:** floods (Euphrates-driven) dominate the *tonnage*; fires are *geographically broad but individually small*. The loss is incremental stress stacked on a drought baseline — a production-shock signal that feeds, but does not replace, a formal GIEWS / FEWS NET / IPC food-security assessment.

### The three research questions

| | Question | Answer | Confidence |
|---|---|---|---|
| **RQ1** | What drove the 2026 floods — rain or upstream river discharge? | **Upstream/transboundary Euphrates discharge** (a sustained dry-season ~1,600 m³/s plateau, ~6× the drought baseline, at *zero* local rain). Natural-vs-managed release: **not asserted** — proportionate to the evidence. | HIGH (source) · LOW (cause) |
| **RQ2** | Are the crop fires linked to armed conflict? | **No** — fires sit no closer to conflict than cropland does in general; they read as a **drought-and-heat agricultural hazard**. (2026 conflict data not yet available; demonstrated on the analogous 2025 season.) | GAP / demonstrated |
| **RQ3** | Where does the damage fall relative to areas of control? | A **descriptive** overlay only — *where* damage lands, never a claim that any administration fared better or worse (contested boundaries). | Descriptive |

---

## How it works

Two parallel pipelines, **one repo, one shared output**. That shared output — `damaged_cropland_ha` per area-of-interest per date — is what makes floods and fires *one* study instead of two.

```
   FLOODS                          FIRES
   Sentinel-1 SAR                  Sentinel-2 (dNBR) + VIIRS active fire
        │                                │
   change-detection                 burn severity ∩ fire-confirmation
   ∩ floodplain ∩ cropland          ∩ cropland
        │                                │
        └────────────┬───────────────────┘
                     ▼
        SHARED DAMAGE SCHEMA  →  damaged_cropland_ha   (per AOI, per date, per severity)
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
   FOOD-SECURITY LAYER       RQ1 / RQ2 / RQ3 analyses
   (loss vs 2025 baseline)
```

**The satellites and what each one is for:**

| Sensor | Used for |
|---|---|
| **Sentinel-1** C-band SAR (VV+VH) | Flood extent — sees water *through cloud*; water reads radar-dark |
| **Sentinel-2** optical (NIR/SWIR → dNBR) | Burn-scar severity |
| **VIIRS 375 m** active fire (NASA FIRMS) | Confirms a burn scar is *fire*, not harvest/ploughing |
| **ESA WorldCover** + **Dynamic World** | Cropland mask (two sources, reconciled with disagreement kept) |
| **JRC Global Surface Water**, **MERIT Hydro (HAND)**, **GLO-30 DEM** | Remove permanent rivers, dry uplands, radar shadow from the flood signal |
| **CHIRPS** rainfall, **GloFAS** river discharge | Drought baseline + flood attribution (RQ1) |

The geospatial engineering — SAR change-detection against an in-season per-orbit median, the 375 m fire-vs-harvest discriminator, metric-area (UTM 37N) discipline, and the Google Earth Engine export constraints — is written up in **[`tracking/GEOSPATIAL_METHODS.md`](tracking/GEOSPATIAL_METHODS.md)**.

---

## What makes it credible

This is a conflict zone with a politically charged dam-attribution question, so the methodology is built around **proportionate, defensible claims**:

- **Human validation gate (non-negotiable).** Flood masks, burn scars, and every `damaged_cropland_ha` derived from them are **Tier-2 human-gated**: they default to `unvalidated`, and **only a human** sets `validated`. The food-security layer and all analyses consume *only* validated records — no agent or automated run can flip that flag.
- **Lower-bound by design.** Conservative detection (open-water-only floods; fires confirmed by an independent thermal sensor) means the headline figures *understate* rather than overstate.
- **Uncertainty made explicit.** Every cropland figure carries a union-vs-intersection range; every known failure mode is documented in the validation packets rather than hidden.
- **Reproducible.** A static, version-controlled report (no live server); all external pulls cached and checkpointed; a verification audit (15 PASS / 0 FAIL / 1 known data-availability gap).

---

## Repository map

| Path | What's there |
|---|---|
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Intent, scope, the locked research questions |
| [`docs/STRUCTURE.md`](docs/STRUCTURE.md) | Architecture, contracts, data sources, validation tiers |
| `aois/` | Canonical governorate AOIs + the reconciled cropland mask |
| `baseline/` | 2025 drought reference (rainfall deficit, NDVI anomaly, production floor) |
| `clients/` | Cached API clients (FIRMS, CHIRPS, ACLED, HDX/GDELT, GloFAS, GEE auth) |
| `pipelines/floods/`, `pipelines/fires/` | The two detection pipelines |
| `food_security/` | Validated damage → production loss → indicative pressure |
| `analysis/` | RQ3 overlay + the reproducibility/verification audit |
| `report/` | The Quarto presentation layer (published to Pages) |
| [`tracking/TECHNICAL_REPORT.md`](tracking/TECHNICAL_REPORT.md) | **Full project-lifecycle write-up** |
| [`tracking/GEOSPATIAL_METHODS.md`](tracking/GEOSPATIAL_METHODS.md) | **How the satellite processing works** |
| [`tracking/DECISIONS.md`](tracking/DECISIONS.md) | Every design decision, with rationale (DEC-001…043) |

---

## Reproduce it

A fresh checkout becomes runnable in three steps. Steps 2–3 are interactive and **human-run once** — agents must not run the auth flow or paste secrets.

**1. Environment** (conda — the geospatial stack comes from conda-forge; native pip wheels are unreliable on Windows):

```bash
conda env create -f environment.yml     # creates the `f_f` env  (or: conda env update -n f_f -f environment.yml)
conda activate f_f
python -c "import geopandas, rasterio, xarray, pandas, ee; print('geo stack OK')"
pytest schema/                           # schema round-trip + validation gate
```

**2. Google Earth Engine auth** (once): `earthengine authenticate`, then set `EE_PROJECT=<your-gcloud-project>` (or drop a service-account key in `secrets/`, see DEC-012). `clients.gee_auth.initialize()` is idempotent and never launches the flow itself.

**3. API credentials** — resolved from gitignored `secrets/secrets.toml`, with a per-key env-var override (DEC-020):

| Source | Config | Get a key |
|---|---|---|
| Earth Engine | `EE_PROJECT` + service-account key in `secrets/` | Google Cloud console |
| NASA FIRMS (VIIRS 375 m) | `[firms].map_key` / `MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| ACLED (RQ2) | `[acled].username`+`password` / `ACLED_EMAIL`+`ACLED_KEY` | https://acleddata.com/register/ |
| HDX (datasets) | none — public CKAN API | https://data.humdata.org/ |
| GDELT (news context) | none — public DOC 2.0 API | https://api.gdeltproject.org/ |

**Build the report:** Quarto is a system install (https://quarto.org), then `quarto render report/`. Rendering is frozen (`freeze: auto`) so it never re-triggers expensive satellite pulls — figures are built from the cached, validated tables.

---

## Scope & honest caveats

- **This is a first-half-2026 case study.** The flood and fire windows cover Mar–Jun 2026; the Syrian harvest/fire season peaks in summer, so the heaviest months are **not yet observed**. Every headline is a **lower bound** — a post-harvest re-run yields the concluded full-year figure with no code change.
- **Field/expert verification is the gold standard** above remote-sensing self-consistency; the Tier-2 gates here were closed by a Syria domain expert.
- **Contested control & dam attribution** are handled descriptively and proportionately — never as causal or comparative claims (see `docs/PRODUCT.md` §5, §9).
