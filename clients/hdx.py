"""HDX + GDELT client for corroborating context (docs/STRUCTURE.md §5).

Two public, key-less sources for **corroborating context** — never primary
measurement (the hectares come from the pipelines, §3.2):

* **HDX** — the Humanitarian Data Exchange CKAN API (``package_search``); finds
  humanitarian datasets (e.g. WFP/FAO/OCHA Syria food-security, displacement),
  including OCHA situation-report datasets.
* **GDELT** — the Global Database of Events, Language & Tone DOC 2.0 API; global
  news search for narrative corroboration of the flood/fire event windows
  (PRODUCT §2). **Replaces ReliefWeb** (DEC-022): ReliefWeb's API was restricted
  to organizations listed with ReliefWeb, whereas GDELT needs no key or listing.

Both are cached (§9). GDELT's public endpoint asks for **≤1 request / 5 s**, so
the client throttles uncached calls and retries once on a 429; cache hits cost
nothing. Licenses vary per provider — confirm per artifact before reuse.

    from clients.hdx import search_hdx, search_gdelt
    datasets = search_hdx("Syria food security", rows=10)
    news = search_gdelt("flood OR Euphrates", "2026-04-01", "2026-06-30")
"""

from __future__ import annotations

import time

import requests

from clients._common import Cache

_HDX_SEARCH = "https://data.humdata.org/api/3/action/package_search"
_GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"
_GDELT_MIN_INTERVAL_S = 5.0  # public endpoint: ≤1 request / 5 s

_cache = Cache("hdx")
_last_gdelt_call: list[float] = [0.0]  # module-level throttle clock


class HdxError(RuntimeError):
    """An HDX or GDELT request failed."""


# --- HDX ----------------------------------------------------------------------

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


# --- GDELT (news corroboration) -----------------------------------------------

def _gdelt_datetime(day: str, *, end: bool) -> str:
    """``YYYY-MM-DD`` → GDELT ``YYYYMMDDHHMMSS`` (UTC), spanning the full day."""
    return day.replace("-", "") + ("235959" if end else "000000")


def _throttle_gdelt() -> None:
    """Sleep so consecutive *uncached* GDELT calls honor the ≤1/5 s limit."""
    elapsed = time.time() - _last_gdelt_call[0]
    if 0 < elapsed < _GDELT_MIN_INTERVAL_S:
        time.sleep(_GDELT_MIN_INTERVAL_S - elapsed)


def _pull_gdelt(query: str, start: str, end: str, maxrecords: int, country: str | None) -> list[dict]:
    full_query = f"{query} sourcecountry:{country}" if country else query
    params = {
        "query": full_query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": maxrecords,
        "startdatetime": _gdelt_datetime(start, end=False),
        "enddatetime": _gdelt_datetime(end, end=True),
        "sort": "datedesc",
    }
    _GDELT_MAX_ATTEMPTS = 4
    for attempt in range(1, _GDELT_MAX_ATTEMPTS + 1):
        _throttle_gdelt()
        resp = requests.get(_GDELT_DOC, params=params, timeout=60)
        _last_gdelt_call[0] = time.time()
        if resp.status_code == 429 and attempt < _GDELT_MAX_ATTEMPTS:
            time.sleep(_GDELT_MIN_INTERVAL_S * attempt)  # escalating backoff
            continue
        if not resp.ok:
            raise HdxError(f"GDELT search failed ({resp.status_code}): {resp.text[:200]}")
        try:
            return resp.json().get("articles", [])
        except ValueError:
            # GDELT returns plain-text errors with a 200 on a bad query.
            raise HdxError(f"GDELT returned a non-JSON body: {resp.text[:200]}")
    raise HdxError(
        f"GDELT rate-limited (429) after {_GDELT_MAX_ATTEMPTS} attempts; "
        "the public endpoint allows ≤1 request / 5 s — slow the call rate."
    )


def search_gdelt(
    query: str,
    start: str,
    end: str,
    *,
    maxrecords: int = 50,
    country: str | None = "Syria",
) -> list[dict]:
    """Search GDELT news articles over [start, end] (inclusive), cached.

    ``query`` is GDELT DOC syntax (keywords, ``OR``, quoted phrases); ``country``
    appends a ``sourcecountry:`` filter (GDELT short name, e.g. ``"Syria"``).
    Returns the ``articles`` list (``url``, ``title``, ``seendate``, ``domain``,
    ``language``, …). Cached per ``(query, start, end, country)`` so a re-run
    never re-pulls (and never re-spends the rate budget).
    """
    articles, _ = _cache.cached(
        ("gdelt", query, start, end, maxrecords, country or ""),
        lambda: _pull_gdelt(query, start, end, maxrecords, country),
        meta={"query": query, "start": start, "end": end, "country": country},
    )
    return articles
