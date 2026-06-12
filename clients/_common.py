"""Shared config + cache infrastructure for the external-source clients.

Implements the §9 contract that every external pull is **cached and
checkpointed** — for rate-limit safety (FIRMS 5,000/10 min, ACLED account tiers)
and reproducibility, and so **retry loops never re-pull**. Each client splits its
work into deterministic request units (one AOI × one window × one source) and
fetches each through :class:`Cache`; a unit already on disk is returned without
touching the network, so a re-run or a mid-pull crash resumes instead of
restarting.

Secrets resolve from ``secrets/secrets.toml`` (gitignored) with an env-var
override, mirroring the service-account-key pattern in ``clients/gee_auth.py``
(DEC-012). Nothing is ever hard-coded.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SECRETS_TOML = _REPO_ROOT / "secrets" / "secrets.toml"
_CACHE_ROOT = _REPO_ROOT / "cache"


class ConfigError(RuntimeError):
    """A required secret/config value is missing from env and secrets.toml."""


@lru_cache(maxsize=1)
def _load_toml() -> dict[str, Any]:
    """Parse secrets/secrets.toml once. Returns {} if absent (env-only setups)."""
    if not _SECRETS_TOML.is_file():
        return {}
    import tomllib  # stdlib (py3.11+); no new dependency

    with open(_SECRETS_TOML, "rb") as fh:
        return tomllib.load(fh)


def secret(
    section: str,
    key: str,
    *,
    env: str | None = None,
    required: bool = True,
    default: str | None = None,
) -> str | None:
    """Resolve a config value: env var first, then ``[section].key`` in secrets.toml.

    Parameters
    ----------
    section, key:
        Location in ``secrets/secrets.toml`` (e.g. ``"firms"``, ``"map_key"``).
    env:
        Optional env var that overrides the file (e.g. ``MAP_KEY``).
    required:
        When True (default) and nothing is found, raise :class:`ConfigError` with
        an actionable remedy rather than returning ``None``.
    default:
        Fallback when not required and nothing is configured.
    """
    if env:
        env_val = os.environ.get(env)
        if env_val:
            return env_val
    file_val = _load_toml().get(section, {}).get(key)
    if file_val is not None:
        return file_val
    if not required:
        return default
    env_hint = f" (or env {env})" if env else ""
    raise ConfigError(
        f"Missing config [{section}].{key} in {_SECRETS_TOML}{env_hint}. "
        f"Add it to secrets/secrets.toml (gitignored) or set the env var."
    )


class Cache:
    """A flat, file-based cache keyed by a hash of the request signature.

    One file per request unit under ``cache/<namespace>/``. JSON payloads are
    wrapped with fetch metadata; text payloads (e.g. FIRMS CSV) are stored raw in
    a sibling ``.txt``. The cache is the checkpoint: :meth:`cached` returns a hit
    without calling ``fetch``, so retries and resumes never re-pull (§9).

    The cache dir is gitignored (``cache/`` in .gitignore) — pulls are
    reproducible from pinned sources and must not bloat the repo.
    """

    def __init__(self, namespace: str, *, root: Path | None = None) -> None:
        self.dir = (root or _CACHE_ROOT) / namespace
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts: Any) -> str:
        """Deterministic 16-hex key from the request signature parts."""
        raw = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str, *, text: bool = False) -> Any | None:
        """Return the cached payload, or None on a miss."""
        path = self.dir / (f"{key}.txt" if text else f"{key}.json")
        if not path.is_file():
            return None
        if text:
            return path.read_text(encoding="utf-8")
        record = json.loads(path.read_text(encoding="utf-8"))
        return record["payload"]

    def put(self, key: str, payload: Any, *, text: bool = False, meta: dict | None = None) -> None:
        """Write a payload to the cache, with fetch metadata for JSON entries."""
        path = self.dir / (f"{key}.txt" if text else f"{key}.json")
        if text:
            path.write_text(payload, encoding="utf-8")
            return
        record = {"fetched_at": _utcstamp(), "meta": meta or {}, "payload": payload}
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    def cached(
        self,
        parts: tuple,
        fetch: Callable[[], Any],
        *,
        text: bool = False,
        meta: dict | None = None,
    ) -> tuple[Any, bool]:
        """Return ``(payload, was_cached)`` for a request unit.

        On a hit, ``fetch`` is **not** called (the §9 no-re-pull guarantee). On a
        miss, ``fetch`` runs, its result is cached, and ``was_cached`` is False.
        """
        key = self.key(*parts)
        hit = self.get(key, text=text)
        if hit is not None:
            return hit, True
        payload = fetch()
        self.put(key, payload, text=text, meta=meta)
        return payload, False


class RateLimiter:
    """Rolling-window transaction budget, persisted so it survives process exits.

    FIRMS allows 5,000 transactions / 10 min per MAP_KEY (§9); ACLED is account-
    tiered. We track transaction timestamps in a small state file under the
    cache namespace and expose :meth:`headroom` so a client can surface remaining
    budget and back off before a 429. Cache hits do **not** consume budget — only
    actual network fetches call :meth:`record`.
    """

    def __init__(self, namespace: str, *, limit: int, window_s: int, root: Path | None = None) -> None:
        self.limit = limit
        self.window_s = window_s
        self._path = (root or _CACHE_ROOT) / namespace / "_transactions.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[float]:
        if not self._path.is_file():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _prune(self, stamps: list[float], now: float) -> list[float]:
        return [t for t in stamps if now - t < self.window_s]

    def record(self, n: int = 1) -> None:
        """Register ``n`` consumed transactions at the current time."""
        now = time.time()
        stamps = self._prune(self._load(), now)
        stamps.extend([now] * n)
        self._path.write_text(json.dumps(stamps), encoding="utf-8")

    def used(self) -> int:
        """Transactions consumed in the current rolling window."""
        return len(self._prune(self._load(), time.time()))

    def headroom(self) -> int:
        """Transactions still available in the current rolling window."""
        return max(0, self.limit - self.used())


def _utcstamp() -> str:
    """ISO-8601 UTC timestamp for cache metadata (provenance, not logic)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- Canonical AOIs (shared asset, §3.1 — no module redefines them) -----------

_AOIS_GEOJSON = _REPO_ROOT / "aois" / "governorates.geojson"


def _ring_bounds(coords: Any, acc: list[float]) -> None:
    """Recursively fold a GeoJSON coordinate tree into [minx, miny, maxx, maxy]."""
    if coords and isinstance(coords[0], (int, float)):
        x, y = coords[0], coords[1]
        acc[0], acc[1] = min(acc[0], x), min(acc[1], y)
        acc[2], acc[3] = max(acc[2], x), max(acc[3], y)
        return
    for part in coords:
        _ring_bounds(part, acc)


@lru_cache(maxsize=1)
def load_aois() -> dict[str, dict[str, Any]]:
    """Load the canonical AOIs (§3.1) keyed by ``aoi_id``, with bbox + geometry.

    Reads ``aois/governorates.geojson`` with the stdlib so the bbox-only clients
    (FIRMS, ACLED) need no geopandas. Each entry carries ``name``, ``pipelines``,
    the GeoJSON ``geometry`` (EPSG:4326), and ``bbox`` = (W, S, E, N).
    """
    with open(_AOIS_GEOJSON, encoding="utf-8") as fh:
        fc = json.load(fh)
    out: dict[str, dict[str, Any]] = {}
    for feat in fc["features"]:
        props = feat["properties"]
        acc = [float("inf"), float("inf"), float("-inf"), float("-inf")]
        _ring_bounds(feat["geometry"]["coordinates"], acc)
        out[props["aoi_id"]] = {
            "name": props["name"],
            "pipelines": props.get("pipelines", []),
            "geometry": feat["geometry"],
            "bbox": tuple(acc),  # (W, S, E, N)
        }
    return out


def aoi_bbox_str(aoi_id: str) -> str:
    """FIRMS-style ``W,S,E,N`` bbox string for a canonical AOI."""
    w, s, e, n = load_aois()[aoi_id]["bbox"]
    return f"{w:.4f},{s:.4f},{e:.4f},{n:.4f}"
