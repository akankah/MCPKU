"""Shared Redis cache helpers for MCP servers.

Usage:
    from mcp_cache import cache_get, cache_set, cache_delete

    data = cache_get("mcp:web:fetch:https://example.com")
    if data is None:
        data = fetch_from_web()
        cache_set("mcp:web:fetch:https://example.com", data, ttl=3600)
    return data

Redis URL from REDIS_URL env var (default: redis://localhost:6379/0).
If Redis unavailable, cache silently degrades (all calls go through).
"""

import os, hashlib

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_cache = None


def _get_redis() -> object | None:
    global _cache
    if _cache is None:
        try:
            import redis as rd
            # socket_timeout prevents 30s hang when Redis is down
            _cache = rd.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            # Test connection immediately
            _cache.ping()
        except (ImportError, Exception):
            _cache = False
    return _cache if _cache is not False else None


def _normalize_key(key: str) -> str:
    if len(key) > 200:
        return "hash:" + hashlib.sha256(key.encode()).hexdigest()[:32]
    return key


def cache_get(key: str) -> str | None:
    r = _get_redis()
    if r is None:
        return None
    try:
        val = r.get(_normalize_key(key))
        return val
    except Exception:
        return None


def cache_set(key: str, value: str, ttl: int = 3600) -> bool:
    r = _get_redis()
    if r is None:
        return False
    try:
        r.setex(_normalize_key(key), ttl, value)
        return True
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    r = _get_redis()
    if r is None:
        return False
    try:
        return bool(r.delete(_normalize_key(key)))
    except Exception:
        return False
