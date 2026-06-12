# Syria 2026 Agricultural Shocks

Data-science study quantifying how the 2026 floods and crop fires reversed
Syria's tentative cereal recovery, measured for food-security impact against the
2025 record-drought baseline. Two pipelines (floods, fires) in one repo emit the
same output — `damaged_cropland_ha` per AOI per date.

**Start here:** intent and research questions in [`docs/PRODUCT.md`](docs/PRODUCT.md);
architecture, contracts, and data sources in [`docs/STRUCTURE.md`](docs/STRUCTURE.md);
how Claude works in this repo in [`CLAUDE.md`](CLAUDE.md). Session plan and
decisions in [`tracking/`](tracking/).

## First-run bootstrap

A fresh checkout becomes runnable in three steps. Steps 2–3 are interactive and
**human-run once** — agents must not run the auth flow or paste secrets.

### 1. Environment (conda, not pip wheels)

The geospatial stack (GDAL/rasterio/geopandas) comes from conda-forge; native
pip wheels are not reliable on Windows (`docs/STRUCTURE.md` §8).

```bash
conda env create -f environment.yml   # first time — creates the `f_f` env
# or, if `f_f` already exists:
conda env update -n f_f -f environment.yml
conda activate f_f
```

Verify the stack imports:

```bash
python -c "import geopandas, rasterio, xarray, pandas, ee; print('geo stack OK')"
pytest schema/                          # schema round-trip + validation gate
```

### 2. Google Earth Engine auth (interactive, once)

```bash
earthengine authenticate                # opens a browser; caches credentials
export EE_PROJECT=<your-gcloud-project> # the Cloud project that bills EE
```

Then, in code:

```python
from clients.gee_auth import initialize
initialize()   # idempotent; reads EE_PROJECT; never re-auths in a retry loop
```

If credentials are missing, `initialize()` raises with the exact
`earthengine authenticate` remedy — it never launches the flow itself.

### 3. API keys (set as environment variables, never hard-coded)

| Variable | For | Where to get it |
|---|---|---|
| `EE_PROJECT` | Earth Engine billing project | Google Cloud console |
| `MAP_KEY` | NASA FIRMS (VIIRS 375 m hotspots) | https://firms.modaps.eosdis.nasa.gov/api/ |
| `ACLED_KEY` / `ACLED_EMAIL` | ACLED conflict events (RQ2) | https://acleddata.com/ |

GloFAS (CDS API), HDX/ReliefWeb, and Copernicus EMS (EMSR811) access paths are
catalogued in the companion dossier (produced in Session 2).

## Presentation layer

A static, reproducible **Quarto** report (`report/`), published as self-contained
HTML — **not** a running dashboard (DEC-008). Quarto is a system install, not a
conda/pip package: see https://quarto.org.

## Validation gate (non-negotiable)

Flood masks, burn scars, and any `damaged_cropland_ha` derived from them are
**Tier-2 human-gated** (`docs/STRUCTURE.md` §6). They default to
`validation_status = unvalidated`; **only a human** sets `validated`. The
food-security layer and RQ analyses consume only validated records
(`DamageRecord.is_consumable()`). No agent or Workflow run may flip that flag.
