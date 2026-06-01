# MCPKU

A personal toolbox of **13 MCP servers** in a single Python repo, all built on
`FastMCP` and exposed over **stdio**. Plug the whole set into opencode, Claude
Desktop, Cursor, or any MCP-compatible client.

> Status: personal project. Tested on Windows / Python 3.11+. See
> [`PATCH_NOTES.md`](PATCH_NOTES.md) for the most recent security and
> correctness fixes.

---

## What's inside

| Server        | File                  | What it gives you                                                         |
|---------------|-----------------------|---------------------------------------------------------------------------|
| `bash`        | `mcp_bash.py`         | Sandboxed shell with command + argument denylist and git-subcommand ACL   |
| `think`       | `mcp_think.py`        | Per-session chain-of-thought scratchpad (`new_session`, `think`, `reset`)  |
| `time`        | `mcp_time.py`         | Current time, timezone conversion, IANA timezone listing                  |
| `filesystem`  | `mcp_filesystem.py`   | Read / write / search / diff inside an allowlisted directory tree         |
| `git`         | `mcp_git.py`          | Status, diff, log, commit, branch, merge, rebase, stash, tag, blame       |
| `github`      | `mcp_github.py`       | ~65 tools: repos, issues, PRs, releases, gists, workflows, alerts, …      |
| `web`         | `mcp_web.py`          | URL fetch (HTML→text or raw) and Firecrawl-backed web search              |
| `vector`      | `mcp_vector.py`       | Postgres + `pgvector` collections, OpenAI embeddings, cosine search       |
| `postgres`    | `mcp_postgres.py`     | Read-only SQL with retry+backoff and a connection pool                    |
| `sqlite`      | `mcp_sqlite.py`       | Read/write queries, schema introspection, identifier-safe PRAGMA          |
| `redis`       | `mcp_redis.py`        | Strings, lists, sets, hashes, TTL, `FLUSHDB` with 2-step confirmation     |
| `memory`      | `mcp_memory.py`       | JSONL-backed knowledge graph (entities, relations, observations)          |
| `browser`     | `mcp_browser.py`      | Headless Chromium via Playwright (snapshot, click, fill, screenshot)      |

`mcp_cache.py` is a shared helper used by `postgres`, `vector`, and `web` for
optional Redis-backed response caching. It is not a standalone server.

---

## Install

Requires **Python 3.10+** on the PATH as `python`.

```bash
pip install "mcp[cli]" \
            redis psycopg2-binary numpy requests \
            GitPython playwright
playwright install chromium
```

That is the full dependency set. Servers that don't need a package
(`bash`, `think`, `time`, `filesystem`, `memory`) will simply not import it.

---

## Environment variables

All env vars are read at server startup. Leave any blank to disable the
matching feature.

| Var                       | Used by                | Notes                                              |
|---------------------------|------------------------|----------------------------------------------------|
| `GITHUB_API_KEY`          | `mcp_github.py`        | Personal access token. Unauthenticated = 60 req/h. |
| `FIRECRAWL_API_KEY`       | `mcp_web.py`           | Required only for `search_web`.                    |
| `OPENAI_API_KEY`          | `mcp_vector.py`        | Embeddings. Falls back to a local hash if missing. |
| `DATABASE_URL`            | `mcp_postgres.py`, `mcp_vector.py` | Standard libpq URL.                    |
| `REDIS_URL`               | `mcp_redis.py`, `mcp_cache.py`     | Default `redis://localhost:6379/0`.    |
| `SQLITE_DB_PATH`          | `mcp_sqlite.py`        | Default = in-memory.                               |
| `MCP_EXTRA_ALLOWED_DIR`   | `mcp_filesystem.py`    | Extra allowlisted root (comma-separated).          |
| `MEMORY_FILE_PATH`        | `mcp_memory.py`        | Default `memory.jsonl` next to the script.         |
| `LOCAL_TIMEZONE`          | `mcp_time.py`          | Default timezone for `get_current_time()`.         |
| `DB_POOL_MIN` / `DB_POOL_MAX` | `mcp_postgres.py`  | Pool sizing. Default 2 / 10.                       |
| `REDIS_POOL_MAX`          | `mcp_redis.py`         | Default 10.                                        |
| `VECTOR_EMBEDDING_MODEL`  | `mcp_vector.py`        | Default `text-embedding-3-small`.                  |
| `VECTOR_EMBEDDING_DIM`    | `mcp_vector.py`        | Default 1536.                                      |

On Windows (PowerShell):

```powershell
$env:GITHUB_API_KEY  = "ghp_..."
$env:FIRECRAWL_API_KEY = "fc-..."
$env:OPENAI_API_KEY  = "sk-..."
$env:DATABASE_URL    = "postgresql://user:pass@localhost:5432/mcpku"
$env:REDIS_URL       = "redis://localhost:6379/0"
```

Persist via System Properties → Environment Variables, or in your shell profile.

---

## Register with an MCP client

### opencode

A working `opencode.jsonc` is checked into the repo root. After `pip install`
and setting the env vars above, **quit and restart opencode** so the config
is reloaded. Run `/mcp` to confirm all 13 servers are connected.

### Claude Desktop

`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "bash":      { "command": "python", "args": ["E:/MCPKU/mcp_bash.py"] },
    "think":     { "command": "python", "args": ["E:/MCPKU/mcp_think.py"] },
    "time":      { "command": "python", "args": ["E:/MCPKU/mcp_time.py"] },
    "filesystem":{ "command": "python", "args": ["E:/MCPKU/mcp_filesystem.py"] },
    "git":       { "command": "python", "args": ["E:/MCPKU/mcp_git.py"] },
    "github":    { "command": "python", "args": ["E:/MCPKU/mcp_github.py"] },
    "web":       { "command": "python", "args": ["E:/MCPKU/mcp_web.py"] },
    "vector":    { "command": "python", "args": ["E:/MCPKU/mcp_vector.py"] },
    "postgres":  { "command": "python", "args": ["E:/MCPKU/mcp_postgres.py"] },
    "sqlite":    { "command": "python", "args": ["E:/MCPKU/mcp_sqlite.py"] },
    "redis":     { "command": "python", "args": ["E:/MCPKU/mcp_redis.py"] },
    "memory":    { "command": "python", "args": ["E:/MCPKU/mcp_memory.py"] },
    "browser":   { "command": "python", "args": ["E:/MCPKU/mcp_browser.py"] }
  }
}
```

### Cursor / others

Same shape — register each `mcp_*.py` as a stdio command. Trim the list to
whatever you actually need; you don't have to enable all 13.

---

## Security model (high level)

- `bash` runs only commands in `ALLOWED_COMMANDS` **and** rejects any argument
  matching `DANGEROUS_ARG_PATTERNS` (wildcard deletes, `-rf`,
  `--no-preserve-root`, subshell syntax, etc.). Git is further restricted to
  an explicit subcommand allowlist.
- `redis.flushdb` is a **two-step** operation: `redis_flushdb_request` issues
  a short-lived token, `redis_flushdb_confirm` consumes it. The token expires
  automatically.
- `sqlite` validates every table identifier with a regex
  (`^[A-Za-z_][A-Za-z0-9_ ]*$`) before interpolating into `PRAGMA`.
- `postgres` is read-only: only `SELECT` / `WITH` / `EXPLAIN` / `SHOW` are
  allowed through `query` / `run_query`.
- `filesystem` is rooted at a fixed allowlist. Set `MCP_EXTRA_ALLOWED_DIR`
  to extend it; the default is intentionally narrow.

See [`PATCH_NOTES.md`](PATCH_NOTES.md) for the full list of fixes and the
remaining known issues.

---

## Development

Each server is a single self-contained file with a `mcp.run(transport="stdio")`
entrypoint. To run one in isolation for debugging:

```bash
python mcp_bash.py
# …or with the MCP Inspector:
mcp dev mcp_bash.py
```

There are no automated tests yet. Adding a `tests/` directory and a few
`pytest` cases per server is the next obvious step — contributions welcome.

---

## License

Personal project. Pick a license before publishing externally.
