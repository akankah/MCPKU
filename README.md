<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-dark.png">
  <img alt="MCPKU" src="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-light.png">
</picture>

**MCPKU** is an open-source **AI Runtime** — a coordinated layer of 15 MCP
servers that gives AI agents the ability to read, write, execute, debug, fix,
and commit code autonomously.

Not a collection of tools. A **closed-loop** for AI-driven development.

```
AI Model
    │  understands intent, generates code
    ▼
MCPKU Runtime
    │  orchestrates: shell → git → web → browser → diagnostics → autofix
    ▼
15 MCP Servers
    │  each a self-contained stdio process
    ▼
Your System / Repo / DB / Browser / Logs
```

> Status: personal project · Tested on Windows / Python 3.11+ ·
> [PATCH_NOTES.md](PATCH_NOTES.md) · [MIT License](LICENSE)

---

## Why MCPKU exists

Most MCP repos ship one tool at a time: a filesystem server, a browser server,
a git server. They solve one problem each.

MCPKU solves a **workflow**: when a command fails, the AI doesn't just see
an error — it can parse, classify, fix, retry, and commit, all within the
same orchestration layer. That's the difference between "AI that assists" and
"AI that builds."

---

## Autonomous Debugging Engine

The heart of MCPKU is its **closed-loop debugging pipeline**:

```
Run command   ──❌──→  Parse traceback  ──→  Classify error
    │                                                    │
    │                                              Apply fix strategy
    │                                                    │
    │                                         ┌──────────┴──────────┐
    │                                         │                     │
    │                                    Fix succeeds        No fix / max retries
    │                                         │                     │
    │                                         │            Search web + GitHub
    │                                         │            for error references
    │                                         │                     │
    └──✅── Retry ──────────── Fix succeeds ───┘                     │
                                      │                              │
                                      │                        AI reads results,
                                      │                        applies fix, retry
                                      │                              │
                                Optional: git commit ──────── retry ─┘
```

This pipeline is implemented across two servers:

| Server        | Role                                          |
|---------------|-----------------------------------------------|
| `diagnostics` | Parse, classify, explain any error (Python / Node.js / Rust / Go) |
| `autofix`     | Apply auto-fix (pip, npm, mkdir, kill-port, go mod tidy, black) + search web + GitHub for unknown errors + retry + commit |

Supported auto-fix strategies:

| Error | Fix |
|---|---|
| `ImportError` / `ModuleNotFoundError` | `pip install <package>` |
| `JS.ModuleNotFound` | `npm install <package>` |
| `FileNotFoundError` / `ENOENT` | `mkdir -p <parent_dir>` |
| `EADDRINUSE` | `taskkill /PID` (Win) / `lsof -ti:PORT \| kill` (Unix) |
| `Go.BuildError` | `go mod tidy` |
| `IndentationError` | `black <file>` |

---

## 15 MCP Servers

Each server is a single self-contained Python file. Enable only what you need.

| Server        | File                  | What it gives you                                                         |
|---------------|-----------------------|---------------------------------------------------------------------------|
| `bash`        | `mcp_bash.py`         | Sandboxed shell with command+argument denylist and git-subcommand ACL     |
| `think`       | `mcp_think.py`        | Per-session chain-of-thought scratchpad (`new_session`, `think`, `reset`) |
| `time`        | `mcp_time.py`         | Current time, timezone conversion, IANA timezone listing                  |
| `filesystem`  | `mcp_filesystem.py`   | Read/write/search/diff inside an allowlisted directory tree               |
| `git`         | `mcp_git.py`          | Status, diff, log, commit, branch, merge, rebase, stash, tag, blame       |
| `github`      | `mcp_github.py`       | ~65 tools: repos, issues, PRs, releases, gists, workflows, alerts        |
| `web`         | `mcp_web.py`          | URL fetch (HTML→text or raw) and Firecrawl-backed web search              |
| `vector`      | `mcp_vector.py`       | Postgres + `pgvector` + OpenAI embeddings, cosine similarity search       |
| `postgres`    | `mcp_postgres.py`     | Read-only SQL with retry+backoff and connection pool                      |
| `sqlite`      | `mcp_sqlite.py`       | Read/write queries, schema introspection, identifier-safe PRAGMA          |
| `redis`       | `mcp_redis.py`        | Strings, lists, sets, hashes, TTL, FLUSHDB with 2-step confirmation       |
| `memory`      | `mcp_memory.py`       | JSONL-backed knowledge graph (entities, relations, observations)          |
| `browser`     | `mcp_browser.py`      | Headless Chromium via Playwright (snapshot, click, fill, screenshot)      |
| `diagnostics` | `mcp_diagnostics.py`  | Auto-parse, classify, and explain errors from any command output          |
| `autofix`     | `mcp_autofix.py`      | Closed-loop debugging + web/GitHub search for unknown errors             |

`mcp_cache.py` is a shared helper for Redis-backed response caching (used by
`postgres`, `vector`, `web`). Not a standalone server.

---

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium
python -m pytest tests/ -v    # 135 tests, ~4 seconds
```

Environment variables (set before starting the MCP client):

| Var | Used by | Notes |
|---|---|---|
| `GITHUB_API_KEY` | `mcp_github.py` | Personal access token |
| `FIRECRAWL_API_KEY` | `mcp_web.py` | Required for web search |
| `OPENAI_API_KEY` | `mcp_vector.py` | Embeddings (falls back to local hash) |
| `DATABASE_URL` | `mcp_postgres.py`, `mcp_vector.py` | Standard libpq URL |
| `REDIS_URL` | `mcp_redis.py`, `mcp_cache.py` | Default `redis://localhost:6379/0` |
| `SQLITE_DB_PATH` | `mcp_sqlite.py` | Default = in-memory |
| `MCP_EXTRA_ALLOWED_DIR` | `mcp_filesystem.py` | Extra allowlisted roots (comma-sep) |
| `MEMORY_FILE_PATH` | `mcp_memory.py` | Default `memory.jsonl` |
| `LOCAL_TIMEZONE` | `mcp_time.py` | Default timezone |

---

## Client configuration

### opencode

`opencode.jsonc` is checked into the repo root. After installing deps and
setting env vars, restart opencode and run `/mcp`.

### Claude Desktop

```json
{
  "mcpServers": {
    "bash":       { "command": "python", "args": ["E:/MCPKU/mcp_bash.py"] },
    "think":      { "command": "python", "args": ["E:/MCPKU/mcp_think.py"] },
    "time":       { "command": "python", "args": ["E:/MCPKU/mcp_time.py"] },
    "filesystem": { "command": "python", "args": ["E:/MCPKU/mcp_filesystem.py"] },
    "git":        { "command": "python", "args": ["E:/MCPKU/mcp_git.py"] },
    "github":     { "command": "python", "args": ["E:/MCPKU/mcp_github.py"] },
    "web":        { "command": "python", "args": ["E:/MCPKU/mcp_web.py"] },
    "vector":     { "command": "python", "args": ["E:/MCPKU/mcp_vector.py"] },
    "postgres":   { "command": "python", "args": ["E:/MCPKU/mcp_postgres.py"] },
    "sqlite":     { "command": "python", "args": ["E:/MCPKU/mcp_sqlite.py"] },
    "redis":      { "command": "python", "args": ["E:/MCPKU/mcp_redis.py"] },
    "memory":     { "command": "python", "args": ["E:/MCPKU/mcp_memory.py"] },
    "browser":    { "command": "python", "args": ["E:/MCPKU/mcp_browser.py"] },
    "diagnostics":{"command": "python", "args": ["E:/MCPKU/mcp_diagnostics.py"] },
    "autofix":    { "command": "python", "args": ["E:/MCPKU/mcp_autofix.py"] }
  }
}
```

### Cursor / others

Same pattern — register each `mcp_*.py` as a stdio command. Trim the list to
whatever you need.

---

## Architecture

Each server is a single file with a `mcp.run(transport="stdio")` entrypoint,
built on `FastMCP`. The orchestrator is implicit: the AI client decides which
server to call based on the `instructions` metadata embedded in each server.

```
User prompt
    │
AI Model
    │  reads instructions: "auto-call parse_traceback on every error"
    ▼
MCPKU Server  ──── stdio ────→  Python process
    │                           │
    │                           ├── mcp_bash.py        (shell)
    │                           ├── mcp_filesystem.py  (file I/O)
    │                           ├── mcp_diagnostics.py (error parsing)
    │                           ├── mcp_autofix.py     (auto-fix loop)
    │                           └── ... (11 more)
    │
    └──→ Returns structured result → AI interprets → next action
```

---

## Security

- `bash` — command allowlist + argument denylist (wildcard deletes, `-rf`,
  subshell injection, etc.). Git restricted to explicit subcommand allowlist.
- `redis.flushdb` — 2-step: request issues a short-lived token, confirm
  consumes it.
- `sqlite` — identifier validation via regex before PRAGMA interpolation.
- `postgres` — read-only: only `SELECT` / `WITH` / `EXPLAIN` / `SHOW`
  allowed.
- `filesystem` — rooted at fixed allowlist. Extend via `MCP_EXTRA_ALLOWED_DIR`.

See [`PATCH_NOTES.md`](PATCH_NOTES.md) for full details.

---

## Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

**135 tests** across 13 server modules. All pure unit tests (no network, DB,
or browser dependency). Runs in ~4 seconds.

| Module | Tests | What's covered |
|---|---|---|
| `test_diagnostics.py` | 33 | Error classification, traceback parsing (Python/Node/Rust), language detection, history |
| `test_bash.py` | 15 | Command allowlist, argument denylist, git ACL, injection blocking |
| `test_autofix.py` | 29 | Fix handlers, module extraction, async run loop with mocked shell |
| `test_sqlite.py` | 13 | Identifier validation, CRUD operations |
| `test_vector.py` | 9 | Fallback embeddings, collection name sanitization |
| `test_postgres.py` | 4 | Retry with exponential backoff |
| `test_*` (6 more) | 32 | Git flag protection, memory persistence, think sessions, timezone, HTML parsing, filesystem paths, Redis flush tokens |

---

## Terminology

| Term | Meaning |
|---|---|
| **MCPKU Runtime** | The orchestration layer of 15 coordinated servers |
| **Autonomous Debugging Engine** | The diagnostics + autofix pipeline that closes the debug loop |
| **Closed-loop debugging** | Run → detect → fix → retry → commit without human intervention |
| **Fix strategy** | A handler function that maps an error type to an executable fix command |
| **AI Runtime** | Infrastructure that lets AI models interact with system resources through MCP |

---

## License

MIT — see [LICENSE](LICENSE).
