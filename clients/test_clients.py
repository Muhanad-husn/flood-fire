"""Tier-1 tests for the external-source clients (docs/STRUCTURE.md §6, §9).

Covers the §9 contract directly: env/secret resolution, the cache hit/miss path,
and — the load-bearing one — that **a simulated retry never re-pulls**. All
network and GEE calls are mocked; each test points the client's cache at a
``tmp_path`` so runs are isolated and hermetic. Run: ``pytest clients/``.
"""

from __future__ import annotations

import pytest

from clients import _common
from clients._common import Cache, ConfigError, RateLimiter, secret


# --- fakes --------------------------------------------------------------------

class FakeResp:
    def __init__(self, *, status=200, text="", json_data=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class Counter:
    """Wraps a response factory and counts how many times it was invoked."""

    def __init__(self, factory):
        self.n = 0
        self._factory = factory

    def __call__(self, *a, **k):
        self.n += 1
        return self._factory(*a, **k)


# --- shared: config -----------------------------------------------------------

def test_secret_env_overrides_file(monkeypatch):
    monkeypatch.setenv("MAP_KEY", "from-env")
    assert secret("firms", "map_key", env="MAP_KEY") == "from-env"


def test_secret_missing_raises_with_remedy(monkeypatch):
    monkeypatch.delenv("DEFINITELY_UNSET", raising=False)
    monkeypatch.setattr(_common, "_load_toml", lambda: {})
    with pytest.raises(ConfigError) as ei:
        secret("nope", "nada", env="DEFINITELY_UNSET")
    assert "secrets.toml" in str(ei.value)


def test_secret_not_required_returns_default(monkeypatch):
    monkeypatch.setattr(_common, "_load_toml", lambda: {})
    assert secret("x", "y", required=False, default="d") == "d"


# --- shared: cache ------------------------------------------------------------

def test_cache_roundtrip_json_and_text(tmp_path):
    c = Cache("ns", root=tmp_path)
    c.put(c.key("a", 1), {"v": 1})
    assert c.get(c.key("a", 1)) == {"v": 1}
    c.put(c.key("t"), "raw,csv\n1,2", text=True)
    assert c.get(c.key("t"), text=True) == "raw,csv\n1,2"
    assert c.get(c.key("missing")) is None


def test_cached_no_repull_on_retry(tmp_path):
    """The §9 guarantee: a second call for the same unit does not call fetch."""
    c = Cache("ns", root=tmp_path)
    fetch = Counter(lambda: {"payload": 42})
    v1, cached1 = c.cached(("k", 1), fetch)
    v2, cached2 = c.cached(("k", 1), fetch)
    assert v1 == v2 == {"payload": 42}
    assert (cached1, cached2) == (False, True)
    assert fetch.n == 1  # fetched exactly once despite two calls


def test_cache_key_is_deterministic_and_order_independent():
    assert Cache.key("a", {"x": 1, "y": 2}) == Cache.key("a", {"y": 2, "x": 1})
    assert Cache.key("a", 1) != Cache.key("a", 2)


# --- shared: rate limiter -----------------------------------------------------

def test_rate_limiter_headroom_and_persistence(tmp_path):
    rl = RateLimiter("ns", limit=100, window_s=600, root=tmp_path)
    assert rl.headroom() == 100
    rl.record(10)
    assert rl.used() == 10 and rl.headroom() == 90
    # A fresh instance reads the persisted state (survives process exit).
    rl2 = RateLimiter("ns", limit=100, window_s=600, root=tmp_path)
    assert rl2.used() == 10


def test_rate_limiter_prunes_old_window(tmp_path, monkeypatch):
    rl = RateLimiter("ns", limit=100, window_s=600, root=tmp_path)
    import clients._common as cc
    t = [1000.0]
    monkeypatch.setattr(cc.time, "time", lambda: t[0])
    rl.record(5)
    assert rl.used() == 5
    t[0] += 601  # advance past the window
    assert rl.used() == 0 and rl.headroom() == 100


# --- FIRMS --------------------------------------------------------------------

_FIRMS_CSV = (
    "latitude,longitude,bright_ti4,acq_date,acq_time,satellite,instrument,confidence,frp,daynight\n"
    "36.13,40.80,311.2,2026-06-10,2254,N,VIIRS,n,1.92,N\n"
)


def _firms_env(tmp_path, monkeypatch):
    import clients.firms as firms
    monkeypatch.setenv("MAP_KEY", "TESTKEY")
    monkeypatch.setattr(firms, "_cache", Cache("firms", root=tmp_path))
    monkeypatch.setattr(firms, "_limiter", RateLimiter("firms", limit=5000, window_s=600, root=tmp_path))
    return firms


def test_firms_chunks_split_at_10_days(tmp_path, monkeypatch):
    firms = _firms_env(tmp_path, monkeypatch)
    chunks = firms._chunks("2026-05-01", "2026-05-25")  # 25 days
    assert [d for _, d in chunks] == [10, 10, 5]


def test_firms_fetch_parses_caches_and_no_repull(tmp_path, monkeypatch):
    firms = _firms_env(tmp_path, monkeypatch)
    get = Counter(lambda *a, **k: FakeResp(text=_FIRMS_CSV))
    monkeypatch.setattr(firms.requests, "get", get)

    rows = firms.fetch_bbox("40,36,42,37", "2026-06-01", "2026-06-03",
                            sources=("VIIRS_SNPP_NRT",), aoi_id="hasakah")
    assert len(rows) == 1
    assert rows[0]["instrument"] == "VIIRS" and rows[0]["aoi_id"] == "hasakah"
    assert rows[0]["source"] == "VIIRS_SNPP_NRT"
    assert get.n == 1
    # Retry: served from cache, no new network call.
    firms.fetch_bbox("40,36,42,37", "2026-06-01", "2026-06-03", sources=("VIIRS_SNPP_NRT",))
    assert get.n == 1
    # The 3-day window consumed 3 transactions of headroom.
    assert firms.rate_limit_headroom() == 5000 - 3


def test_firms_rejects_invalid_key(tmp_path, monkeypatch):
    firms = _firms_env(tmp_path, monkeypatch)
    monkeypatch.setattr(firms.requests, "get", lambda *a, **k: FakeResp(text="Invalid MAP_KEY."))
    with pytest.raises(firms.FirmsError):
        firms.fetch_bbox("40,36,42,37", "2026-06-01", "2026-06-01", sources=("VIIRS_SNPP_NRT",))


def test_firms_blocks_when_over_budget(tmp_path, monkeypatch):
    firms = _firms_env(tmp_path, monkeypatch)
    firms._limiter.record(4999)  # only 1 transaction left
    monkeypatch.setattr(firms.requests, "get", lambda *a, **k: FakeResp(text=_FIRMS_CSV))
    with pytest.raises(firms.FirmsError, match="headroom"):
        firms.fetch_bbox("40,36,42,37", "2026-06-01", "2026-06-05", sources=("VIIRS_SNPP_NRT",))


# --- CHIRPS -------------------------------------------------------------------

def test_chirps_caches_and_never_repulls_gee(tmp_path, monkeypatch):
    import clients.chirps as chirps
    monkeypatch.setattr(chirps, "_cache", Cache("chirps", root=tmp_path))
    series = [{"date": "2025-01-01", "precip_mm": 0.3}]
    pull = Counter(lambda *a, **k: series)
    monkeypatch.setattr(chirps, "_pull_series", pull)

    out1 = chirps.fetch_daily("deir_ez_zor", "2025-01-01", "2025-01-01")
    out2 = chirps.fetch_daily("deir_ez_zor", "2025-01-01", "2025-01-01")
    assert out1 == out2 == series
    assert pull.n == 1  # GEE hit once; retry served from cache
    assert chirps.season_total_mm("deir_ez_zor", "2025-01-01", "2025-01-01") == pytest.approx(0.3)


def test_chirps_unknown_aoi_raises(tmp_path, monkeypatch):
    import clients.chirps as chirps
    monkeypatch.setattr(chirps, "_cache", Cache("chirps", root=tmp_path))
    with pytest.raises(chirps.ChirpsError):
        chirps.fetch_daily("atlantis", "2025-01-01", "2025-01-02")


# --- ACLED --------------------------------------------------------------------

def _acled_env(tmp_path, monkeypatch):
    import clients.acled as acled
    monkeypatch.setattr(acled, "_cache", Cache("acled", root=tmp_path))
    monkeypatch.setattr(acled, "_TOKEN_PATH", tmp_path / "acled" / "_token.json")
    monkeypatch.setattr(acled, "_creds", lambda: ("user@org", "pw"))
    return acled


def test_acled_password_grant_then_cached_token(tmp_path, monkeypatch):
    acled = _acled_env(tmp_path, monkeypatch)
    post = Counter(lambda *a, **k: FakeResp(json_data={
        "access_token": "AT", "refresh_token": "RT", "expires_in": 86400, "token_type": "Bearer"}))
    monkeypatch.setattr(acled.requests, "post", post)

    assert acled._access_token() == "AT"
    assert acled._access_token() == "AT"   # second call uses cached state
    assert post.n == 1                      # no second token mint


def test_acled_refreshes_when_access_expired(tmp_path, monkeypatch):
    acled = _acled_env(tmp_path, monkeypatch)
    # Seed an expired access token but a still-valid refresh token.
    import time as _t
    acled._write_token_state({
        "access_token": "OLD", "refresh_token": "RT",
        "access_expires_at": _t.time() - 10, "refresh_expires_at": _t.time() + 9999})
    post = Counter(lambda url, data=None, **k: FakeResp(json_data={
        "access_token": "NEW", "refresh_token": "RT2", "expires_in": 86400}))
    monkeypatch.setattr(acled.requests, "post", post)

    assert acled._access_token() == "NEW"
    # Verify it used the refresh grant, not a password grant.
    assert post.n == 1


def test_acled_paginates_and_caches_per_page(tmp_path, monkeypatch):
    acled = _acled_env(tmp_path, monkeypatch)
    monkeypatch.setattr(acled, "_PAGE_SIZE", 2)
    monkeypatch.setattr(acled, "_access_token", lambda: "AT")

    pages = {1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}  # page2 short -> stop

    def fake_get(url, headers=None, params=None, timeout=None):
        return FakeResp(json_data={"success": True, "data": pages[params["page"]]})

    get = Counter(fake_get)
    monkeypatch.setattr(acled.requests, "get", get)

    rows = acled.fetch_events("2026-05-01", "2026-07-31", country="Syria")
    assert [r["id"] for r in rows] == [1, 2, 3]
    assert get.n == 2  # two pages fetched
    # Retry: both pages served from cache, no new requests.
    acled.fetch_events("2026-05-01", "2026-07-31", country="Syria")
    assert get.n == 2


def test_acled_aoi_maps_to_live_admin1(tmp_path, monkeypatch):
    acled = _acled_env(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(acled, "fetch_events",
                        lambda s, e, admin1=None, **k: seen.update(admin1=admin1) or [])
    acled.fetch_events_for_aoi("hasakah", "2026-05-01", "2026-07-31")
    assert seen["admin1"] == "Al Hasakeh"  # confirmed live string, not a guess
    with pytest.raises(acled.AcledError):
        acled.fetch_events_for_aoi("atlantis", "2026-05-01", "2026-07-31")


def test_acled_retries_once_on_401(tmp_path, monkeypatch):
    acled = _acled_env(tmp_path, monkeypatch)
    monkeypatch.setattr(acled, "_PAGE_SIZE", 100)
    monkeypatch.setattr(acled, "_access_token", lambda: "AT")
    seq = [FakeResp(status=401, text="expired"),
           FakeResp(json_data={"success": True, "data": [{"id": 1}]})]
    monkeypatch.setattr(acled.requests, "get", lambda *a, **k: seq.pop(0))
    rows = acled.fetch_events("2026-05-01", "2026-05-31")
    assert [r["id"] for r in rows] == [1]


# --- HDX / ReliefWeb ----------------------------------------------------------

def test_hdx_search_caches_and_no_repull(tmp_path, monkeypatch):
    import clients.hdx as hdx
    monkeypatch.setattr(hdx, "_cache", Cache("hdx", root=tmp_path))
    get = Counter(lambda *a, **k: FakeResp(json_data={
        "success": True, "result": {"results": [{"name": "syria-food-security"}]}}))
    monkeypatch.setattr(hdx.requests, "get", get)

    r1 = hdx.search_hdx("Syria food security", rows=5)
    r2 = hdx.search_hdx("Syria food security", rows=5)
    assert r1 == r2 == [{"name": "syria-food-security"}]
    assert get.n == 1


def test_gdelt_search_caches_and_no_repull(tmp_path, monkeypatch):
    import clients.hdx as hdx
    monkeypatch.setattr(hdx, "_cache", Cache("hdx", root=tmp_path))
    monkeypatch.setattr(hdx.time, "sleep", lambda *_: None)  # no real throttling in tests
    get = Counter(lambda *a, **k: FakeResp(json_data={"articles": [{"title": "Euphrates floods"}]}))
    monkeypatch.setattr(hdx.requests, "get", get)

    out = hdx.search_gdelt("flood OR Euphrates", "2026-04-01", "2026-06-30")
    assert out == [{"title": "Euphrates floods"}]
    assert get.n == 1
    hdx.search_gdelt("flood OR Euphrates", "2026-04-01", "2026-06-30")  # cache hit
    assert get.n == 1


def test_gdelt_retries_once_on_429(tmp_path, monkeypatch):
    import clients.hdx as hdx
    monkeypatch.setattr(hdx, "_cache", Cache("hdx", root=tmp_path))
    monkeypatch.setattr(hdx.time, "sleep", lambda *_: None)
    seq = [FakeResp(status=429, text="slow down"),
           FakeResp(json_data={"articles": [{"title": "ok"}]})]
    monkeypatch.setattr(hdx.requests, "get", lambda *a, **k: seq.pop(0))
    assert hdx.search_gdelt("fire", "2026-05-01", "2026-07-31") == [{"title": "ok"}]


def test_gdelt_datetime_spans_full_days():
    import clients.hdx as hdx
    assert hdx._gdelt_datetime("2026-04-01", end=False) == "20260401000000"
    assert hdx._gdelt_datetime("2026-06-30", end=True) == "20260630235959"
