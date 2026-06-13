"""GloFAS river-discharge client — Copernicus Early Warning Data Store (RQ1/S9).

Role: the **upstream-discharge** half of the RQ1 rainfall-vs-release decomposition
(`docs/PRODUCT.md` §5 Secondary-1). CHIRPS (`clients/chirps.py`) gives the local
rainfall signal; this client gives the Euphrates / Khabur reach discharge from the
GloFAS-ERA5 / LISFLOOD reanalysis, to be read against the reported ~2,000 m3/s
surge vs the 200–250 m3/s drought baseline (`docs/PRODUCT.md` §2).

Dataset (dossier §4.3): **`cems-glofas-historical`** on the EWDS
(`ewds.climate.copernicus.eu`), variable
``river_discharge_in_the_last_24_hours`` (m3/s), v4 LISFLOOD. Two product types:

* ``consolidated`` — GloFAS-ERA5, accurate but lags ~6 months (no recent window).
* ``intermediate`` — operational analysis, ~2–5 day lag (covers the 2026 window).

The retrieve is gridded global; we subset server-side with ``area`` [N,W,S,E] to
the Euphrates corridor. **Two human prerequisites** (one-time):

1. Accept the dataset licence at
   ``…/datasets/cems-glofas-historical?tab=download#manage-licences`` — otherwise
   the retrieve 403s ("required licences not accepted").
2. A valid EWDS ``url``+``key`` in ``secrets/secrets.toml`` ``[cds]`` (DEC-034).

Every retrieve is cached as the downloaded NetCDF under ``cache/glofas/`` keyed by
the request signature; a re-run or retry reuses the file and never re-submits the
CDS job (§9 no-re-pull). Point extraction (main-stem cell selection) is pure-local
on the cached cube.

    from clients.glofas import discharge_series_at, EUPHRATES_POINTS
    series = discharge_series_at(EUPHRATES_POINTS, 2026, [3,4,5,6])
    # -> {"euphrates_deir_ez_zor": [{"date","discharge_m3s"}, ...], ...}
"""

from __future__ import annotations

from calendar import monthrange
from pathlib import Path
from typing import Any

from clients._common import ConfigError, secret, _CACHE_ROOT  # noqa: F401 (root reuse)

DATASET = "cems-glofas-historical"
VARIABLE = "river_discharge_in_the_last_24_hours"
SYSTEM_VERSION = "version_4_0"
HYDRO_MODEL = "lisflood"

# Euphrates corridor [N, W, S, E] — from the Turkish border (Jarabulus) through
# Raqqa and Deir ez-Zor, plus the Khabur through Hasakah.
CORRIDOR_AREA = [37.3, 37.5, 34.5, 41.2]

# Reach extraction points (lon, lat). The Euphrates main stem is transboundary
# (>90% of flow originates upstream in Turkey); the Khabur is a local rain-fed
# tributary — that contrast is the spine of the attribution.
EUPHRATES_POINTS: dict[str, tuple[float, float]] = {
    "euphrates_border_jarabulus": (38.01, 36.82),   # inflow from Turkey
    "euphrates_below_tabqa": (38.56, 35.87),        # below Syria's main dam / Lake Assad
    "euphrates_raqqa": (39.01, 35.95),              # flood AOI
    "euphrates_deir_ez_zor": (40.14, 35.34),        # flood AOI (downstream)
    "khabur_hasakah": (40.75, 36.51),               # local rain-fed tributary (Hasakah)
}

_CACHE_DIR = _CACHE_ROOT / "glofas"


class GlofasError(RuntimeError):
    """A GloFAS retrieve or extraction failed."""


def _client():
    """Construct the EWDS cdsapi client from secrets (env override supported)."""
    try:
        import cdsapi
    except ImportError as exc:  # pragma: no cover - env guard
        raise GlofasError(
            "cdsapi is not installed; add it to environment.yml (conda-forge)."
        ) from exc
    url = secret("cds", "url", env="CDSAPI_URL")
    key = secret("cds", "key", env="CDSAPI_KEY")
    return cdsapi.Client(url=url, key=key)


def _request(year: int, months: list[int], product_type: str, area: list[float]) -> dict:
    """Build the cems-glofas-historical retrieve request for whole month(s)."""
    days = sorted({d for m in months for d in range(1, monthrange(year, m)[1] + 1)})
    return {
        "system_version": [SYSTEM_VERSION],
        "hydrological_model": [HYDRO_MODEL],
        "product_type": [product_type],
        "variable": VARIABLE,
        "hyear": [str(year)],
        "hmonth": [f"{m:02d}" for m in months],
        "hday": [f"{d:02d}" for d in days],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": area,
    }


def _signature(year: int, months: list[int], product_type: str, area: list[float]) -> str:
    from clients._common import Cache

    return Cache.key(DATASET, year, sorted(months), product_type, area)


def fetch_discharge_nc(
    year: int,
    months: list[int],
    *,
    product_type: str = "intermediate",
    area: list[float] | None = None,
) -> Path:
    """Download (or reuse cached) the GloFAS discharge NetCDF for a window.

    The cube is one ``area``-subset month-set for one product type, cached as
    ``cache/glofas/<sig>.nc``. A re-run or retry returns the existing file without
    re-submitting the CDS job (§9). Raises :class:`GlofasError` on retrieve failure
    (incl. the licence-not-accepted 403 — accept the licence at the EWDS portal).
    """
    area = area or CORRIDOR_AREA
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = _CACHE_DIR / f"{_signature(year, months, product_type, area)}.nc"
    if target.is_file() and target.stat().st_size > 0:
        return target

    req = _request(year, months, product_type, area)
    try:
        _client().retrieve(DATASET, req, str(target))
    except Exception as exc:
        # Clean up any partial file so a retry re-pulls cleanly.
        if target.is_file():
            target.unlink()
        msg = str(exc)
        if "licence" in msg.lower() or "403" in msg:
            raise GlofasError(
                "GloFAS retrieve forbidden — accept the cems-glofas-historical licence at "
                "https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical"
                "?tab=download#manage-licences (same account as the API key)."
            ) from exc
        raise GlofasError(f"GloFAS retrieve failed ({product_type} {year} {months}): {exc}") from exc
    if not (target.is_file() and target.stat().st_size > 0):
        raise GlofasError(f"GloFAS retrieve produced no data for {product_type} {year} {months}.")
    return target


def _open_cube(nc_path: Path):
    """Open the GloFAS NetCDF and return (DataArray dis24, lon_name, lat_name)."""
    import xarray as xr

    ds = xr.open_dataset(nc_path)
    # Discharge variable name varies by product/version: dis24 / discharge / the
    # long name. Pick the first data var carrying discharge units/dims.
    candidates = [v for v in ds.data_vars if "dis" in v.lower()] or list(ds.data_vars)
    da = ds[candidates[0]]
    lon_name = "longitude" if "longitude" in da.coords else ("lon" if "lon" in da.coords else None)
    lat_name = "latitude" if "latitude" in da.coords else ("lat" if "lat" in da.coords else None)
    if lon_name is None or lat_name is None:
        raise GlofasError(f"Could not find lon/lat coords in {nc_path} (coords={list(da.coords)}).")
    return da, lon_name, lat_name


def _series_at_point(
    da, lon_name: str, lat_name: str, lon: float, lat: float, *, radius_cells: int = 3
) -> list[dict]:
    """Extract the daily discharge series at the main-stem cell near (lon, lat).

    GloFAS resolves a river only on its channel cells; the nearest grid cell to a
    map point may sit off-channel. Within a ``radius_cells`` window we pick the cell
    with the **largest mean discharge** — the main channel — which avoids needing
    the static upstream-area map. Returns ``[{"date","discharge_m3s"}, ...]``.
    """
    import numpy as np

    lons = da[lon_name].values
    lats = da[lat_name].values
    ix = int(np.abs(lons - lon).argmin())
    iy = int(np.abs(lats - lat).argmin())
    x0, x1 = max(0, ix - radius_cells), min(len(lons), ix + radius_cells + 1)
    y0, y1 = max(0, iy - radius_cells), min(len(lats), iy + radius_cells + 1)

    win = da.isel({lon_name: slice(x0, x1), lat_name: slice(y0, y1)})
    # Collapse time to a mean per cell to find the channel, then pick that cell.
    time_dim = [d for d in win.dims if d not in (lon_name, lat_name)]
    cell_mean = win.mean(dim=time_dim) if time_dim else win
    flat = cell_mean.values
    if np.all(np.isnan(flat)):
        raise GlofasError(f"No valid GloFAS discharge near ({lon},{lat}).")
    j, i = np.unravel_index(np.nanargmax(flat), flat.shape)
    cell = win.isel({lat_name: j, lon_name: i})

    tname = time_dim[0] if time_dim else None
    out = []
    if tname is None:
        return out
    times = cell[tname].values
    vals = cell.values
    for t, v in zip(times, vals):
        date = str(np.datetime_as_string(t, unit="D"))
        out.append({"date": date, "discharge_m3s": (float(v) if not np.isnan(v) else None)})
    return out


def discharge_series_at(
    points: dict[str, tuple[float, float]],
    year: int,
    months: list[int],
    *,
    product_type: str = "intermediate",
    area: list[float] | None = None,
    radius_cells: int = 3,
) -> dict[str, list[dict]]:
    """Daily GloFAS discharge series at each named reach point, cached upstream.

    Pulls one ``area``-subset cube for the window (cached NetCDF), then extracts the
    main-stem series per point locally. Returns ``{point_name: [{date, discharge_m3s}]}``.
    """
    nc = fetch_discharge_nc(year, months, product_type=product_type, area=area)
    da, lon_name, lat_name = _open_cube(nc)
    return {
        name: _series_at_point(da, lon_name, lat_name, lon, lat, radius_cells=radius_cells)
        for name, (lon, lat) in points.items()
    }
