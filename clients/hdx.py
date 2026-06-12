"""HDX / ReliefWeb client (docs/STRUCTURE.md §5).

Two public, key-less APIs for **corroborating context** — never primary
measurement (the hectares come from the pipelines, §3.2):

* **HDX** — the Humanitarian Data Exchange CKAN API (``package_search``); finds
  humanitarian datasets (e.g. WFP/FAO/OCHA Syria food-security, displacement).
* **ReliefWeb** — situation reports / news for narrative corroboration of the
  flood and fire event windows (PRODUCT §2).

Both are cached (§9); ReliefWeb asks every caller to pass an ``appname``. Licenses
vary per provider (often CC-BY / CC-BY-IGO) — confirm per artifact before reuse.

    from clients.hdx import search_hdx, search_reliefweb
    datasets = search_hdx("Syria food security", rows=10)
    reports  = search_reliefweb("Deir ez-Zor floods", country="Syrian Arab Republic")
"""

from __future__ import annotations

import requests

from clients._common import Cache, secret

_HDX_SEARCH = "https://data.humdata.org/api/3/action/package_search"
# ReliefWeb v1 was decommissioned (HTTP 410); v2 requires a *pre-approved*
# appname (register at https://apidoc.reliefweb.int/parameters#appname). The
# appname is read from config so a registered name drops in without a code change.
_RELIEFWEB_REPORTS = "https://api.reliefweb.int/v2/reports"
_DEFAULT_APPNAME = "syria-2026-agri-shocks"  # placeholder until one is registered

_cache = Cache("hdx")


def _reliefweb_appname() -> str:
    return secret("reliefweb", "appname", env="RELIEFWEB_APPNAME",
                  required=False, default=_DEFAULT_APPNAME)


class HdxError(RuntimeError):
    """An HDX or ReliefWeb request failed."""


def _pull_hdx(query: str, rows: int, fq: str | None) -> list[dict]:
    params = {"q": query, "rows": rows}
    if fq:
        params["fq"] = fq
    resp = requests.get(_HDX_SEARCH, params=params, timeout=60)
    if not resp.ok:
        raise HdxError(f"HDX search failed ({resp.status_code}): {resp.text[:200]}")
    body = resp.json()
    if not body.get("success", False):
        raise HdxError(f"HDX returned success=false: {body.get('error')}")
    return body.get("result", {}).get("results", [])


def search_hdx(query: str, *, rows: int = 20, fq: str | None = None) -> list[dict]:
    """Search HDX datasets (cached). Returns the CKAN ``results`` list.

    ``fq`` is a CKAN filter query, e.g. ``'groups:syr'`` to scope to Syria.
    """
    results, _ = _cache.cached(
        ("hdx", query, rows, fq or ""),
        lambda: _pull_hdx(query, rows, fq),
        meta={"query": query, "rows": rows, "fq": fq},
    )
    return results


def _pull_reliefweb(query: str, limit: int, country: str | None) -> list[dict]:
    payload: dict = {
        "query": {"value": query, "operator": "AND"},
        "limit": limit,
        "fields": {"include": ["title", "date.created", "source.shortname", "url", "country"]},
        "sort": ["date.created:desc"],
    }
    if country:
        payload["filter"] = {"field": "country", "value": country}
    # v2 takes appname as a query param (not in the body).
    resp = requests.post(
        _RELIEFWEB_REPORTS, params={"appname": _reliefweb_appname()}, json=payload, timeout=60
    )
    if resp.status_code == 403:
        raise HdxError(
            "ReliefWeb v2 rejected the appname. Register one at "
            "https://apidoc.reliefweb.int/parameters#appname and set it as "
            "[reliefweb].appname in secrets.toml (or env RELIEFWEB_APPNAME)."
        )
    if not resp.ok:
        raise HdxError(f"ReliefWeb search failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json().get("data", [])


def search_reliefweb(
    query: str, *, limit: int = 20, country: str | None = "Syrian Arab Republic"
) -> list[dict]:
    """Search ReliefWeb reports (cached). Returns the ``data`` list of hits."""
    data, _ = _cache.cached(
        ("reliefweb", query, limit, country or ""),
        lambda: _pull_reliefweb(query, limit, country),
        meta={"query": query, "limit": limit, "country": country},
    )
    return data
