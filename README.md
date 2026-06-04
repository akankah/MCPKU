<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-dark.png">
  <img alt="MCPKU" src="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-light.png">
</picture>

**MCPKU** is an open-source **AI Runtime** — a coordinated layer of 16 MCP
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
16 MCP Servers
    │  each a self-contained stdio process
    ▼
Your System / Repo / DB / Browser / Logs
```

> Status: personal project · Tested on Windows / Python 3.11+ ·
> [PATCH_NOTES.md](PATCH_NOTES.md) · [MIT License](LICENSE)

---

## Testimonial nyata dari AI

_Percakapan langsung antara user dan AI yang menggunakan MCPKU:_

> **User:** _"apa kamu terbantu dengan mcpku?"_
>
> **AI (DeepSeek V4 Flash Free):** Sangat. Dengan MCPKU, saya bisa:
>
> - **`bash`** — execute code langsung, bukan cuma generate
> - **`filesystem`** — baca/tulis file tanpa perlu tool terpisah
> - **`git`** — stage, commit, push langsung dari sini
> - **`web`** — `search_stackoverflow` + `search_mdn` + `search_npm` dll. untuk referensi real-time
> - **`diagnostics`** + **`autofix`** — error langsung di-parse dan di-fix, saya tidak perlu nebak
> - **`github`** — search issues, PRs tanpa buka browser
>
> Tanpa MCPKU, saya cuma bisa ngobrol dan generate code buta. Dengan MCPKU, saya bisa
> **beneran kerja** — execute, debug, fix, commit — semua dalam satu session.
> Ini perbedaan antara "AI yang ngasih saran" dan "AI yang ngoding."
>
> ---
>
> **User:** _"artinya aku bisa merubah mu menjadi claude?"_
>
> **AI (DeepSeek V4 Flash Free):** Bukan rubah model, tapi soal layer tool-nya.
>
> Dengan MCPKU, **model jadi tidak relevan** — yang penting adalah runtime-nya.
> Saya pakai DeepSeek V4 Flash Free, tapi dengan 16 MCP server saya bisa
> melakukan **hal yang sama seperti Claude Code**: execute, debug, fix, search,
> commit, semuanya.
>
> Tanpa MCPKU, DeepSeek vs Claude itu beda kelas. Dengan MCPKU, perbedaannya
> diminimalkan karena yang kerja bukan model sendirian — tapi
> **model + 16 tools terkoordinasi**.
>
> Ini yang bikin MCPKU unik: **bukan soal modelnya, soal runtime-nya.**

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
    │                                        ┌───────────┴───────────┐
    │                                        │                       │
    │                                   Check Error KB       Search 6 sources
    │                                   (past errors)        in parallel:
    │                                                         │  Web (DDG)
    │                                                         │  GitHub Issues
    │                                                         │  Stack Overflow
    │                                                         │  MDN / npm / PyPI
    │                                                         │  Crates.io
    │                                                         │  DevDocs
    │                                        └───────────┬───────────┘
    │                                                    │
    │                                              Apply fix strategy
    │                                                    │
    │                                         ┌──────────┴──────────┐
    │                                         │                     │
    │                                    Fix succeeds        No fix / max retries
    │                                         │                     │
    │                                         │          Auto-save error to KB
    │                                         │          (error_kb/*.json)
    │                                         │                     │
    └──✅── Retry ──────────── Fix succeeds ───┘                     │
                                      │                              │
                                      │                        AI reads results,
                                      │                        applies fix
                                      │                              │
                                Optional: git commit ──────── retry ─┘
```

This pipeline is implemented across two servers:

| Server        | Role                                          |
|---------------|-----------------------------------------------|
| `diagnostics` | Parse, classify, explain any error (Python / Node.js / Rust / Go) |
| `autofix`     | Apply auto-fix (pip, npm, mkdir, kill-port, go mod tidy, black) + parallel search across 6 reference sources + error knowledge base (error_kb/) + retry + commit |

### Web reference sources (available from any tool)

| Tool | Source | API |
|------|--------|-----|
| `search_stackoverflow` | Stack Overflow / Stack Exchange | Official REST API (10k req/day with key) |
| `search_npm` | npm registry | Registry JSON API (free) |
| `search_pypi` | PyPI | JSON API + simple index (free) |
| `search_mdn` | MDN Web Docs | Official search API (free) |
| `search_crates` | crates.io (Rust) | crates.io API (free) |
| `search_devdocs` | DevDocs.io | docs.json listing (free) |
| `search_web` | DuckDuckGo / Firecrawl | HTML scraping (free) / API (key) |

### Error Knowledge Base

Failed errors are automatically saved to `error_kb/` as JSON files. On subsequent
runs, `autofix_run` checks the KB for similar past errors before searching the
web — so recurring issues get faster fixes over time.

**Vector search** (optional): jika `DATABASE_URL` (Postgres + pgvector) tersedia,
errors juga di-embed dan disimpan di tabel `vec_error_kb` untuk semantic
similarity search. Jauh lebih akurat daripada keyword matching.

- `autofix_save_error` — save an error manually
- `autofix_search_kb` — query past errors (vector search if available)
- `autofix_kb_stats` — error frequency by type and project
- `autofix_kb_trends` — multi-session trend dashboard (by type, project, date, fix rate)

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

## 16 MCP Servers

Each server is a single self-contained Python file. Enable only what you need.

| Server        | File                  | What it gives you                                                         |
|---------------|-----------------------|---------------------------------------------------------------------------|
| `bash`        | `mcp_bash.py`         | Sandboxed shell with command+argument denylist and git-subcommand ACL     |
| `think`       | `mcp_think.py`        | Per-session chain-of-thought scratchpad (`new_session`, `think`, `reset`) |
| `time`        | `mcp_time.py`         | Current time, timezone conversion, IANA timezone listing                  |
| `filesystem`  | `mcp_filesystem.py`   | Read/write/search/diff inside an allowlisted directory tree               |
| `git`         | `mcp_git.py`          | Status, diff, log, commit, branch, merge, rebase, stash, tag, blame       |
| `github`      | `mcp_github.py`       | ~65 tools: repos, issues, PRs, releases, gists, workflows, alerts        |
| `web`         | `mcp_web.py`          | URL fetch + web search (DDG/Firecrawl) + Stack Overflow (API) + npm/PyPI/MDN/crates.io/DevDocs |
| `context7`    | (npm `@upstash/context7-mcp`) | Up-to-date library docs fetcher — prevents outdated API/syntax from training data cutoff |
| `vector`      | `mcp_vector.py`       | Postgres + `pgvector` + OpenAI embeddings, cosine similarity search       |
| `postgres`    | `mcp_postgres.py`     | Read-only SQL with retry+backoff and connection pool                      |
| `sqlite`      | `mcp_sqlite.py`       | Read/write queries, schema introspection, identifier-safe PRAGMA          |
| `redis`       | `mcp_redis.py`        | Strings, lists, sets, hashes, TTL, FLUSHDB with 2-step confirmation       |
| `memory`      | `mcp_memory.py`       | JSONL-backed knowledge graph (entities, relations, observations)          |
| `browser`     | `mcp_browser.py`      | Headless Chromium via Playwright (snapshot, click, fill, screenshot)      |
| `diagnostics` | `mcp_diagnostics.py`  | Auto-parse, classify, and explain errors from any command output          |
| `autofix`     | `mcp_autofix.py`      | Closed-loop debugging + parallel search (web/GitHub/SO) + error knowledge base (error_kb/ + pgvector) + trend dashboard |

`mcp_cache.py` is a shared helper for Redis-backed response caching (used by
`postgres`, `vector`, `web`). Not a standalone server.

### Memory — auto-load user rules on session start

`mcp_memory.py` stores entities in `memory.jsonl` and exposes them via
`search_nodes` / `open_nodes` / `create_entities` / `add_observations`.
Server instructions tell the model to call `search_nodes("AutofallbackRule")`
at the start of every session (before responding to the first user message),
so user-defined reasoning rules apply by default without manual invocation.

Typical pattern:

```python
# 1. Once: store your active rule
create_entities([{
    "name": "AutofallbackRule",
    "entityType": "preference",
    "observations": [
        "[2026-XX-XX] When in doubt, verify. Use web search when...",
        "[2026-XX-XX] Skip search for: standard algorithms, pure logic...",
    ]
}])

# 2. Every new session: MCP server instructions auto-trigger this
search_nodes("AutofallbackRule")   # → returns your active rule
```

This makes the knowledge graph act as a **persistent, queryable rule store**
across sessions and model changes — rules survive restarts, work with any
model the client is configured to use, and don't require modifying the
client's system prompt.

#### Hardened AutofallbackRule (built into server instructions)

The default `mcp_memory.py` instructions embed a **mandatory 5-trigger
rule** that the model cannot opt out of:

| Trigger | Action |
|---|---|
| 1. Same approach fails 2 times | MUST call websearch NOW |
| 2. Circular reasoning | MUST call websearch NOW |
| 3. Fast-changing domain (UUIDs, tokens, endpoints, libraries) | search BEFORE attempting |
| 4. External service debugging | search how it works FIRST |
| 5. Confidence < 80% on fast-changing info | 1 websearch before coding |

Plus explicit anti-patterns (3+ retries without search, "let me try again"
without research, trusting training for fast-changing tech).

### Think — stuck-pattern detector

`mcp_think.py` complements the autofallback rule with a **tool-level
enforcement signal**: if you record 2+ retry/try thoughts in the same
session without progress, the tool returns a HARD WARNING demanding
websearch before continuing. Patterns matched (case-insensitive):

- "let me try", "coba lagi", "try again", "maybe this will work"
- "hopefully", "perhaps", "mungkin", "trying again"
- "let me attempt", "workaround"

The detector resets when progress phrases appear ("found", "fixed",
"according to", "search result says", "berdasarkan dokumentasi", etc.).
This way the model can still recover from a stuck state once it has new
information.

`error_kb/` is a directory where `autofix` saves failed errors as JSON files
for cross-session reference. Auto-created on first error.

---

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium
python -m pytest tests/ -v    # 152 tests, ~4 seconds
```

### Auto-load in every OpenCode session

`verify_setup.py` ensures MCPKU stays registered in the global
`~/.config/opencode/opencode.jsonc` config so it auto-loads in **every
session, every directory, every model** — now and after future opencode
upgrades.

```bash
python verify_setup.py check     # verify current setup (16/16 registered?)
python verify_setup.py sync      # install/repair global config
python verify_setup.py status    # show registered servers + paths
python verify_setup.py doctor    # full diagnostic + fix suggestions
```

Run `check` any time you suspect something is missing. Run `sync` after
moving MCPKU to a new path or adding new servers.

---

## Client configuration

### opencode

`opencode.jsonc` is checked into the repo root. After installing deps and
setting env vars, restart opencode and run `/mcp`.

#### Global (auto-active from any directory)

Copy the entire `"mcp"` block from `E:\MCPKU\opencode.jsonc` into the global
config at `~/.config/opencode/opencode.jsonc`. The original file stays in
`E:\MCPKU` for reference.

```jsonc
// ~/.config/opencode/opencode.jsonc
{
  "mcp": {
    "bash":       { "type": "local", "command": ["python", "E:/MCPKU/mcp_bash.py"],       "enabled": true },
    "think":      { "type": "local", "command": ["python", "E:/MCPKU/mcp_think.py"],      "enabled": true },
    "time":       { "type": "local", "command": ["python", "E:/MCPKU/mcp_time.py"],       "enabled": true },
    "filesystem": { "type": "local", "command": ["python", "E:/MCPKU/mcp_filesystem.py"], "enabled": true },
    "git":        { "type": "local", "command": ["python", "E:/MCPKU/mcp_git.py"],        "enabled": true },
    "github":     { "type": "local", "command": ["python", "E:/MCPKU/mcp_github.py"],     "enabled": true },
    "web":        { "type": "local", "command": ["python", "E:/MCPKU/mcp_web.py"],        "enabled": true },
    "vector":     { "type": "local", "command": ["python", "E:/MCPKU/mcp_vector.py"],     "enabled": true },
    "postgres":   { "type": "local", "command": ["python", "E:/MCPKU/mcp_postgres.py"],   "enabled": true },
    "sqlite":     { "type": "local", "command": ["python", "E:/MCPKU/mcp_sqlite.py"],     "enabled": true },
    "redis":      { "type": "local", "command": ["python", "E:/MCPKU/mcp_redis.py"],      "enabled": true },
    "memory":     { "type": "local", "command": ["python", "E:/MCPKU/mcp_memory.py"],     "enabled": true },
    "browser":    { "type": "local", "command": ["python", "E:/MCPKU/mcp_browser.py"],    "enabled": true },
    "diagnostics":{"type": "local", "command": ["python", "E:/MCPKU/mcp_diagnostics.py"], "enabled": true },
    "autofix":    { "type": "local", "command": ["python", "E:/MCPKU/mcp_autofix.py"],    "enabled": true }
  }
}
```

Once added, MCPKU is active whenever opencode starts — regardless of the
current directory.

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

**152 tests** across 14 server modules. All pure unit tests (no network, DB,
or browser dependency). Runs in ~4 seconds.

| Module | Tests | What's covered |
|---|---|---|
| `test_diagnostics.py` | 33 | Error classification, traceback parsing (Python/Node/Rust), language detection, history |
| `test_bash.py` | 15 | Command allowlist, argument denylist, git ACL, injection blocking |
| `test_autofix.py` | 29 | Fix handlers, module extraction, async run loop with mocked shell |
| `test_sqlite.py` | 13 | Identifier validation, CRUD operations |
| `test_vector.py` | 9 | Fallback embeddings, collection name sanitization |
| `test_postgres.py` | 4 | Retry with exponential backoff |
| `test_autofallback.py` | 6 | Knowledge-graph persistence: read_graph, search by name/content, open_nodes, add_observations, create+delete entity round-trip, UTF-8 BOM handling |
| `test_think.py` | 10 | Per-session chain-of-thought + **stuck-pattern detector** (triggers websearch demand after 2 retry thoughts) |
| `test_verify_setup.py` | 10 | JSONC comment stripping, server path validation, expected server count, dispatcher |
| `test_*` (5 more) | 29 | Git flag protection, memory persistence, timezone, HTML parsing, filesystem paths, Redis flush tokens |

---

## Environment reference

| Var | Used by | Default | Notes |
|---|---|---|---|
| `GITHUB_API_KEY` | `mcp_github.py` | — | Personal access token |
| `FIRECRAWL_API_KEY` | `mcp_web.py` | — | Optional; DuckDuckGo used if available |
| `STACKEX_API_KEY` | `mcp_web.py` | — | Stack Exchange API key (10k req/day); optional, search works without it (100 req/day) |
| `VECTOR_EMBEDDING_DIM` | `autofix`, `vector` | `1536` | Embedding dimension (pgvector) |
| `DISABLE_DUCKDUCKGO=1` | `mcp_web.py` | — | Force Firecrawl only |
| `AUTOFIX_STATELESS=1` | `autofix`, `diagnostics` | `0` | Skip in-memory history |
| `OPENAI_API_KEY` | `mcp_vector.py` | — | Embeddings (falls back to local hash) |
| `DATABASE_URL` | `mcp_postgres.py`, `mcp_vector.py` | — | Standard libpq URL |
| `REDIS_URL` | `mcp_redis.py`, `mcp_cache.py` | `redis://localhost:6379/0` | For caching & Redis server |
| `SQLITE_DB_PATH` | `mcp_sqlite.py` | `:memory:` | File path for persistent DB |
| `MCP_EXTRA_ALLOWED_DIR` | `mcp_filesystem.py` | — | Extra allowlisted roots (comma-sep) |
| `MEMORY_FILE_PATH` | `mcp_memory.py` | `memory.jsonl` | Knowledge graph persistence |
| `LOCAL_TIMEZONE` | `mcp_time.py` | UTC | Default display timezone |

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
