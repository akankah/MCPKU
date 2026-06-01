import os, json, time, threading, secrets
from mcp.server.fastmcp import FastMCP

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
POOL_MAX = int(os.environ.get("REDIS_POOL_MAX", "10"))

_pool = None
_pool_lock = threading.Lock()
_r_client = None

# Token konfirmasi flushdb — harus di-request dulu sebelum flush
_flush_tokens: dict[str, float] = {}  # token -> expire_timestamp
_FLUSH_TOKEN_TTL = 60  # detik

mcp = FastMCP("redis-memory", instructions="""
Redis-powered high-speed memory and caching.
Use for: key-value memory, LLM response caching, session state,
knowledge graph entities, and pub/sub event-driven workflows.

Config via env:
  REDIS_URL        Redis connection URL (default: redis://localhost:6379/0)
  REDIS_POOL_MAX   Max connections in pool (default: 10)
""")


def _r():
    global _pool, _r_client
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                import redis as rd
                _pool = rd.ConnectionPool.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    max_connections=POOL_MAX,
                    socket_connect_timeout=5,
                    socket_timeout=10,
                    socket_keepalive=True,
                    health_check_interval=30,
                )
                _r_client = rd.Redis(connection_pool=_pool)
    return _r_client


def _ok(msg: str = "ok") -> str:
    return json.dumps({"status": "ok", "message": msg})


def _err(msg: str) -> str:
    return json.dumps({"status": "error", "message": str(msg)})


@mcp.tool(name="redis_set", description="Set a key-value pair with optional TTL (seconds). TTL=0 means no expiry.")
async def redis_set(key: str, value: str, ttl: int = 0) -> str:
    try:
        r = _r()
        r.set(key, value)
        if ttl > 0:
            r.expire(key, ttl)
        return _ok(f"key '{key}' set ({len(value)} bytes)")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_get", description="Get value for a key. Returns null if key doesn't exist.")
async def redis_get(key: str) -> str:
    try:
        r = _r()
        val = r.get(key)
        if val is None:
            return json.dumps({"key": key, "value": None, "exists": False})
        ttl = r.ttl(key)
        return json.dumps({"key": key, "value": val, "exists": True, "ttl": ttl})
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_delete", description="Delete one or more keys.")
async def redis_delete(keys: list) -> str:
    try:
        r = _r()
        count = r.delete(*keys)
        return _ok(f"deleted {count} keys")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_cache", description="Cache-aware setter: sets key with default TTL=3600s.")
async def redis_cache(key: str, value: str, ttl: int = 3600) -> str:
    try:
        r = _r()
        r.setex(key, ttl, value)
        return _ok(f"cached '{key}' TTL={ttl}s")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_keys", description="Search keys by glob pattern (e.g. 'session:*', 'memory:*').")
async def redis_keys(pattern: str = "*") -> str:
    try:
        r = _r()
        keys = r.keys(pattern)
        if not keys:
            return json.dumps({"keys": [], "count": 0})
        info = []
        for k in sorted(keys):
            ttl = r.ttl(k)
            size = r.strlen(k)
            info.append({"key": k, "ttl": ttl, "bytes": size})
        return json.dumps({"keys": info, "count": len(info)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_lpush", description="Push values to the head of a list.")
async def redis_lpush(key: str, values: list) -> str:
    try:
        r = _r()
        count = r.lpush(key, *values)
        return _ok(f"pushed {len(values)} items, list length={count}")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_lrange", description="Get range of elements from a list. start=0, end=-1 means all.")
async def redis_lrange(key: str, start: int = 0, end: int = -1) -> str:
    try:
        r = _r()
        items = r.lrange(key, start, end)
        return json.dumps({"key": key, "items": items, "count": len(items)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_sadd", description="Add members to a set (ensures uniqueness).")
async def redis_sadd(key: str, members: list) -> str:
    try:
        r = _r()
        count = r.sadd(key, *members)
        return _ok(f"added {count} new members to set '{key}'")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_smembers", description="Get all members of a set.")
async def redis_smembers(key: str) -> str:
    try:
        r = _r()
        members = list(r.smembers(key))
        return json.dumps({"key": key, "members": members, "count": len(members)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_hset", description="Set fields in a hash (for structured data).")
async def redis_hset(key: str, fields: dict) -> str:
    try:
        r = _r()
        r.hset(key, mapping=fields)
        return _ok(f"hash '{key}' updated with {len(fields)} fields")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_hgetall", description="Get all fields and values from a hash.")
async def redis_hgetall(key: str) -> str:
    try:
        r = _r()
        data = r.hgetall(key)
        return json.dumps({"key": key, "fields": data, "count": len(data)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_ttl", description="Get remaining TTL for a key. -1=no expiry, -2=not found.")
async def redis_ttl(key: str) -> str:
    try:
        r = _r()
        ttl = r.ttl(key)
        exists = r.exists(key)
        return json.dumps({"key": key, "ttl": ttl, "exists": bool(exists)})
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_expire", description="Set TTL on an existing key.")
async def redis_expire(key: str, ttl: int) -> str:
    try:
        r = _r()
        ok = r.expire(key, ttl)
        return _ok(f"expire set: {ok}") if ok else _err("key not found")
    except Exception as e:
        return _err(e)


@mcp.tool(
    name="redis_flushdb_request",
    description=(
        "Minta token konfirmasi untuk flushdb. "
        "Token ini berlaku 60 detik dan harus diberikan ke redis_flushdb_confirm. "
        "PERINGATAN: operasi ini akan menghapus SEMUA key di database Redis aktif."
    )
)
async def redis_flushdb_request() -> str:
    token = secrets.token_hex(8)
    _flush_tokens[token] = time.time() + _FLUSH_TOKEN_TTL
    return json.dumps({
        "status": "confirmation_required",
        "message": "PERINGATAN: Ini akan menghapus SEMUA data Redis. Berikan token ini ke redis_flushdb_confirm dalam 60 detik.",
        "confirmation_token": token,
    })


@mcp.tool(
    name="redis_flushdb_confirm",
    description="Konfirmasi flushdb dengan token dari redis_flushdb_request. Token hanya valid 60 detik."
)
async def redis_flushdb_confirm(confirmation_token: str) -> str:
    now = time.time()
    # Hapus token yang sudah expired
    expired = [t for t, exp in _flush_tokens.items() if exp < now]
    for t in expired:
        _flush_tokens.pop(t, None)

    if confirmation_token not in _flush_tokens:
        return _err("token tidak valid atau sudah expired. Minta token baru dengan redis_flushdb_request.")

    _flush_tokens.pop(confirmation_token)
    try:
        r = _r()
        r.flushdb()
        return _ok("database flushed — semua key dihapus")
    except Exception as e:
        return _err(e)


@mcp.tool(name="redis_info", description="Get Redis server info: version, memory, clients, keyspace.")
async def redis_info() -> str:
    try:
        r = _r()
        info = r.info()
        return json.dumps({
            "redis_version": info.get("redis_version", ""),
            "used_memory_human": info.get("used_memory_human", ""),
            "connected_clients": info.get("connected_clients", 0),
            "uptime_in_days": info.get("uptime_in_days", 0),
            "total_keys": sum(
                int(v.get("keys", 0) or 0)
                for v in info.get("keyspace", {}).values()
            ),
            "os": info.get("os", ""),
            "arch_bits": info.get("arch_bits", ""),
        }, indent=2)
    except Exception as e:
        return _err(e)


if __name__ == "__main__":
    mcp.run(transport="stdio")
