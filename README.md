# MCPKU

A standalone collection of 14 MCP (Model Context Protocol) servers — runnable as separate stdio processes via [FastMCP](https://github.com/modelcontextprotocol/python-sdk). Drop them into any MCP-aware client (opencode, Claude Desktop, etc.).

Each server is a single Python file, self-contained, with its own tools and (where needed) env-var configuration. No package install required beyond the `mcp` SDK and a few listed dependencies.

## Servers

| Server | File | Tools | External deps | Env vars |
|---|---|---|---|---|
| `bash` | `mcp_bash.py` | 1 | stdlib | — |
| `browser` | `mcp_browser.py` | 2 | playwright + chromium | — |
| `cache` | `mcp_cache.py` | 0 (helpers) | redis (optional) | `REDIS_URL` |
| `filesystem` | `mcp_filesystem.py` | 20 | stdlib | `MCP_EXTRA_ALLOWED_DIR` |
| `git` | `mcp_git.py` | 18 | gitpython | — |
| `github` | `mcp_github.py` | 68 | requests, python-dotenv | `GITHUB_API_KEY` |
| `memory` | `mcp_memory.py` | 9 | stdlib | `MEMORY_FILE_PATH` |
| `postgres` | `mcp_postgres.py` | 4 | psycopg2-binary | `DATABASE_URL`, `DB_POOL_MIN`, `DB_POOL_MAX` |
| `redis` | `mcp_redis.py` | 15 | redis | `REDIS_URL`, `REDIS_POOL_MAX` |
| `sqlite` | `mcp_sqlite.py` | 6 | stdlib | `SQLITE_DB_PATH` |
| `think` | `mcp_think.py` | 2 | stdlib | — |
| `time` | `mcp_time.py` | 3 | stdlib (zoneinfo) | `LOCAL_TIMEZONE` |
| `vector` | `mcp_vector.py` | 6 | psycopg2-binary, numpy, openai | `DATABASE_URL`, `OPENAI_API_KEY`, `VECTOR_EMBEDDING_MODEL`, `VECTOR_EMBEDDING_DIM` |
| `web` | `mcp_web.py` | 2 | requests | `FIRECRAWL_API_KEY` |

## Quick Start

```bash
# Install runtime deps
pip install mcp requests python-dotenv GitPython playwright psycopg2-binary redis numpy openai
playwright install chromium

# Run any server directly (stdio JSON-RPC)
python mcp_think.py
```

### opencode

Add to `opencode.jsonc`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "bash":      { "type": "local", "command": ["python", "mcp_bash.py"],      "enabled": true, "env": { "PYTHONPATH": "." } },
    "browser":   { "type": "local", "command": ["python", "mcp_browser.py"],   "enabled": true, "env": { "PYTHONPATH": "." } },
    "filesystem":{ "type": "local", "command": ["python", "mcp_filesystem.py"],"enabled": true, "env": { "PYTHONPATH": "." } },
    "git":       { "type": "local", "command": ["python", "mcp_git.py"],       "enabled": true, "env": { "PYTHONPATH": "." } },
    "github":    { "type": "local", "command": ["python", "mcp_github.py"],    "enabled": true, "env": { "PYTHONPATH": ".", "GITHUB_API_KEY": "" } },
    "memory":    { "type": "local", "command": ["python", "mcp_memory.py"],    "enabled": true, "env": { "PYTHONPATH": ".", "MEMORY_FILE_PATH": "./memory.jsonl" } },
    "postgres":  { "type": "local", "command": ["python", "mcp_postgres.py"],  "enabled": true, "env": { "PYTHONPATH": ".", "DATABASE_URL": "" } },
    "redis":     { "type": "local", "command": ["python", "mcp_redis.py"],     "enabled": true, "env": { "PYTHONPATH": ".", "REDIS_URL": "redis://localhost:6379/0" } },
    "sqlite":    { "type": "local", "command": ["python", "mcp_sqlite.py"],    "enabled": true, "env": { "PYTHONPATH": ".", "SQLITE_DB_PATH": "" } },
    "think":     { "type": "local", "command": ["python", "mcp_think.py"],     "enabled": true, "env": { "PYTHONPATH": "." } },
    "time":      { "type": "local", "command": ["python", "mcp_time.py"],      "enabled": true, "env": { "PYTHONPATH": ".", "LOCAL_TIMEZONE": "Asia/Jakarta" } },
    "vector":    { "type": "local", "command": ["python", "mcp_vector.py"],    "enabled": true, "env": { "PYTHONPATH": ".", "DATABASE_URL": "", "OPENAI_API_KEY": "" } },
    "web":       { "type": "local", "command": ["python", "mcp_web.py"],       "enabled": true, "env": { "PYTHONPATH": ".", "FIRECRAWL_API_KEY": "" } }
  }
}
```

Set `PYTHONPATH` (or run opencode from this directory) so the `from mcp_cache import …` relative import resolves for `mcp_postgres`, `mcp_vector`, and `mcp_web`.

## Environment Variables

| Variable | Used by | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | postgres, vector | — | PostgreSQL DSN, e.g. `postgresql://user:pass@host/db` |
| `DB_POOL_MIN` / `DB_POOL_MAX` | postgres | 2 / 10 | psycopg2 connection pool size |
| `REDIS_URL` | redis, cache | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_POOL_MAX` | redis | 10 | Max pooled connections |
| `GITHUB_API_KEY` | github | — | GitHub Personal Access Token |
| `FIRECRAWL_API_KEY` | web (search only) | — | Firecrawl API key for `search_web` |
| `OPENAI_API_KEY` | vector | — | OpenAI key for embeddings (falls back to hash-based if unset) |
| `VECTOR_EMBEDDING_MODEL` | vector | `text-embedding-3-small` | OpenAI embedding model |
| `VECTOR_EMBEDDING_DIM` | vector | 1536 | Embedding vector dimension |
| `SQLITE_DB_PATH` | sqlite | — | Path to `.db` file (created if missing) |
| `MEMORY_FILE_PATH` | memory | `./memory.jsonl` | Knowledge-graph persistence file |
| `LOCAL_TIMEZONE` | time | `UTC` | IANA tz for `get_current_time` default |
| `MCP_EXTRA_ALLOWED_DIR` | filesystem | — | Extra allowed dir appended to allowlist |

## Caching

`mcp_cache` is a shared Redis-backed helper used by `mcp_postgres`, `mcp_vector`, and `mcp_web` to cache results. If Redis is unreachable, calls fall through silently (no errors).

- `mcp_web.fetch_url` — 1h TTL · `search_web` — 30 min
- `mcp_postgres.list_tables` / `describe_table` — 1h · `query` — 5 min
- `mcp_vector` embeddings — 24h

Append `?nocache=true` to any `fetch_url` URL to bypass the cache.

## Architecture

Each file is a standalone FastMCP server:

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("name", instructions="...")

@mcp.tool(name="...", description="...")
async def my_tool(...): ...

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

All servers communicate via JSON-RPC 2.0 over stdio — drop them into any MCP client without modification.

## License

MIT
