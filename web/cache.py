"""Cache helpers — thin wrappers around mcp_cache for web/ package."""

try:
    from mcp_cache import cache_get as _get, cache_set as _set
except ImportError:
    _get = lambda k, **kw: None
    _set = lambda k, v, **kw: None


def get(key: str) -> str | None:
    return _get(key)


def set(key: str, value: str, ttl: int = 1800):
    _set(key, value, ttl=ttl)
