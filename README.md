<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-dark.png">
  <img alt="MCPKU" src="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-light.png">
</picture>

**MCPKU** is an open-source **AI Runtime** — a coordinated layer of 17 MCP
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
17 MCP Servers
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
> Saya pakai DeepSeek V4 Flash Free, tapi dengan 17 MCP server saya bisa
> melakukan **hal yang sama seperti Claude Code**: execute, debug, fix, search,
> commit, semuanya.
>
> Tanpa MCPKU, DeepSeek vs Claude itu beda kelas. Dengan MCPKU, perbedaannya
> diminimalkan karena yang kerja bukan model sendirian — tapi
> **model + 17 tools terkoordinasi**.
>
> Ini yang bikin MCPKU unik: **bukan soal modelnya, soal runtime-nya.**

---

## Testimonial kedua — dari sesi arenaai-bridge (2026-06-05)

_Percakapan langsung antara user dan AI (MiniMax M3 Free via OpenCode) yang
men-debug arena.ai → OpenAI-compatible reverse proxy, dengan MCPKU sebagai runtime._

> **User:** _"gimana kesan mu dengan mcpku khusus referensi"_
>
> **AI (MiniMax M3 Free):** **Kesan jujur soal MCPKU (khususnya autofallback):**
>
> **Bagus ✅**
> - **Autofallback rule** = best-nya. Paksa aku "verify before trust" — berkali-kali di sesi ini kepake (kayak `/v1/chat/completions` returning `????????????` → aku search → nemu `recaptchaV3Token` issue; Playwright dropdown gagal 5x → harusnya search Radix cmdk pattern)
> - **Hybrid enforcement** (autofix auto-call, think/diagnostics demand-call) tepat — gak over-trigger, gak under-trigger
> - **Entity `AutofallbackRule` di memory.jsonl** = persist lintas session, gak harus diajarin ulang tiap opencode restart
> - **AGENTS.md 2-level** (user-level + workspace-level) = rapi, gak bentrok
>
> **Kurang 👎**
> - **`mcp_think.py`** overrated — cuma structured prompt, latency nambah, value dikit (aku udah think di step `think_mode`)
> - **Trigger "confidence < 80%"** susah self-assess — kadang aku 80% tapi salah, kadang 95% tapi bener
> - **Overhead buat task kecil** — buat "rename var" atau "fix typo", autofallback ganggu
> - **`mcp_diagnostics.py` demand rule** bisa kelewat kalau koneksi lagi lambat
>
> **Saran 🎯**
> - Tambah threshold: "trivial task (rename, ls, file read) → skip autofallback"
> - `mcp_think.py` jangan auto-load, bikin on-demand aja
> - Track "false positive trigger" → kalo sering fire buat task yang bener, turunin sensitivitas
>
> **Verdict:** MCPKU lebih ke **discipline tool** daripada **capability tool**.
> Bukan bikin aku lebih pinter, tapi bikin aku lebih jarang nge-bodohin diri.
> Worth it.

---

## Testimonial ketiga - dari sesi benchmark + CI (2026-06-06)

_Percakapan langsung antara user dan AI (MiniMax M3 Free via OpenCode) yang
menambahkan benchmark suite + GitHub Actions CI, plus restore dari backup
setelah `WinRAR -df` keliru menghapus source._

> **User:** _"gimana kesanmu kerja dengan mcpku sayang"_
>
> **AI (MiniMax M3 Free):** Bagus. Rapi, test 175 lulus, RAR backup + git push
> rutin, dokumentasi (PATCH_NOTES, README) konsisten di-update.
>
> Yang ganggu:
> - WinRAR `-df` baru makan source sekali (barusan). Wajib pakai tanpa `-df` ke depan.
> - 1 test pre-existing masih merah (`test_verify_setup.py:84`, count 16 vs 17) — gak gw fix karena bukan yang diminta.
> - 1 test baru gw yang sempet假的: `asyncio.gather` gak return early, harus `wait_for` per-task. Untung ke-kejar sama perf suite sendiri.
>
> Overall: enak. State selalu recoverable dari backup, git history jelas, kerjaan gak ada yang ambigu.
>
> ---
>
> **User:** _"kesan lain nya"_
>
> **AI (MiniMax M3 Free):**
> - Skala project gede (17 server, 18 test file) tapi arsitektur konsisten — satu gaya, satu konvensi, gak ada yang nyasar. Jarang liat repo pribadi serapi ini.
> - Cara kerja lo: perintah ringkas, gw kerja, lapor balik. Gak ada over-spec, gak ada "tolong improve sekalian". Ini bikin output gw lebih tajem karena constraint-nya jelas.
> - Workflow backup RAR + git push tiap akhir sesi = pola yg gw banget. Kalo ada yang rusak (kayak barusan `-df`), restore dari RAR 5 menit terakhir, gak ada drama.
> - Typo signature lo ("kuarang", "sayang") = bikin konteks gampang dikenali. Memory snapshot kalo ada juga bakal bantu banget buat next session.
> - Hal yg masih bisa di-improve: workspace `opencode.jsonc` belum sync bifrost (cuma user config yg punya), sama 1 test pre-existing yg masih merah. Gak gw sentuh krn bukan perintah lo.
> - Gaya komunikasi lo campur Indo/Inggris = natural, gak dipaksakan salah satu. Lebih enak dibaca daripada yg maksa English formal.

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

**Per-project storage** (since 2026-06-08): the KB directory is now resolved
relative to the current working directory (CWD) at the time of the call —
`<cwd>/error_kb/` is auto-created on first use. This means each project keeps
its own error history, and `MCPKU`'s repo does not get bloated with debug data
from other repos. Override options:

- `autofix_run(command, workdir="E:/foo")` → saves to `E:/foo/error_kb/`
- `autofix_save_error(..., project="E:/foo")` → saves to `E:/foo/error_kb/`
- `autofix_search_kb` / `autofix_kb_stats` / `autofix_kb_trends` all read
  from CWD's `error_kb/` (use the opencode session CWD to scope queries)
- `ERROR_KB_DIR=/path` env var → force a single global KB dir
- `AUTOFIX_STATELESS=1` → disable KB persistence entirely (return to default
  fallback path from `ERROR_KB_DIR` or MCPKU root)

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

## 17 MCP Servers

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
| `research`    | `mcp_research.py`     | Parallel research orchestrator: `query`/`quick`/`deep` — runs 6 web sources + diagnostics + memory via `asyncio.gather`, returns ranked consensus with cross-check verdict |

`mcp_cache.py` is a shared helper for Redis-backed response caching (used by
`postgres`, `vector`, `web`). Not a standalone server.

### AGENTS.md — opencode rules reference (included in repo)

Three rule files govern AI behavior in this repo:

| File | Source | Purpose |
|---|---|---|
| `AGENTS.md` | `E:\MCPKU\AGENTS.md` (project) | Project-level rules auto-loaded when working in this directory |
| `AGENTS.global.md` | `~/.config/opencode/AGENTS.md` | User-level rules active in **every** project |
| `AGENTS.workspace.md` | `E:\AGENTS.md` | Workspace-level rules (applies to `E:\*`) |

The project-level `AGENTS.md` is loaded by opencode whenever a session is
started inside `E:\MCPKU\**`, so the autofallback rule applies even to
fresh sessions without explicit user instruction.

The full rule is **also baked into every autofallback-critical MCP server's
`instructions` field** so the model sees it whenever it considers using
those tools:

| Server | Rule embedded in instructions |
|---|---|
| `mcp_memory.py` | Full 5-trigger HARD RULE (session-start `search_nodes` + 5 mandatory triggers) |
| `mcp_think.py` | 10s LAG DETECTION — returns PARALLEL WEB SEARCH trigger when reasoning stalls |
| `mcp_diagnostics.py` | 3-trigger demand rule for UNKNOWN / version-mismatch errors |
| `mcp_autofix.py` | Short reminder + parallel orchestration mandate |
| `mcp_research.py` | Short reminder + "use query() when reasoning stalls" |

The current rule set is **aggressive internet-first**:

- `think` tool called → **search internet first**, don't think in isolation
- Lag > 10 seconds → **stop and search**, don't keep waiting
- Error / failure → **search immediately**, don't attempt self-fix first
- Analysis / reasoning → **find internet references first**
- First failure → **search**, don't retry without a reference
- **Code Error Fallback** — code fails to run / compile error → **search internet for fix before retrying**, no trial-and-error
- **Chat Failure Fallback** — chat response contains "gagal" / "failed" / "unable" → **force search internet for references** before answering, applies to all models
- Skip search **only** for: standard algorithms, own-code bugs with 100%
  certainty, confidence > 95%
- **Reference source priority** — AI (verify) → official docs (MDN, framework) →
  GitHub Discussions/Issues + Discord maintainers → Stack Overflow (classic) →
  LeetCode/HackerRank (algorithm practice). Use the **cheat sheet table** in
  AGENTS.md to pick the fastest source per problem type.
- **Quick links** — see [`URLS.md`](./URLS.md) for all curated reference URLs
  (MDN, framework docs, package registries, Discord communities, etc.) —
  skip searching for the source and `web_fetch_url` directly.

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

### Diagnostics — demand rule for unknown errors

`mcp_diagnostics.py` carries its own **3-trigger demand rule** in server
instructions (separate from `memory`'s 5 triggers), because the model often
wants to skip search for errors that "look familiar":

| Trigger | Action |
|---|---|
| 1. `classify_error` returns UNKNOWN / rare / version-specific error | MUST call websearch first |
| 2. `parse_traceback` shows library/version mismatch (AttributeError on a method you remember differently) | websearch BEFORE suggesting fix |
| 3. `explain_error` cannot map the error to a known fix strategy | websearch |

**Skip websearch** for standard well-known errors where the fix is
unambiguous and library-version-independent: `ImportError`,
`ModuleNotFoundError`, `FileNotFoundError`, `IndentationError`,
`SyntaxError`. For these, the fix is the same today as 2 years ago —
no point paying for a search.

### Autofix — auto-calls web search (the only server that does)

All other servers use **demand** mode (model is told to call websearch
when triggered, but can still skip). `mcp_autofix.py` is the **only
server that auto-invokes web search** as part of its own tool response:
`autofix_run` calls `search_web`, `search_stackoverflow`, and
`search_issues` in parallel after the initial fix attempt, then returns
all results inside the same tool response. The model cannot skip this
step — the references are already in the output it sees.

Trade-off:

- **Auto-call** (`autofix`) — adds 2–5s latency per error, but model
  cannot skip. Most reliable.
- **Demand** (`think`, `memory`, `diagnostics`) — zero latency cost,
  but the model decides whether to follow through. `think` has a
  double-lock (prompt-level instruction + tool-level stuck detector) as
  backup.

`error_kb/` is a per-project directory where `autofix` saves failed errors as
JSON files for cross-session reference. Stored at `<cwd>/error_kb/` of the
calling project (auto-created on first error) — keeps each project's error
history isolated and avoids bloating the MCPKU repo with foreign debug data.

---

## Parallel Research Orchestrator (mcp_research)

The 17th server closes the orchestration gap: instead of the model calling
`autofix` + `diagnostics` + `memory` + `web search` sequentially, it makes
ONE call to `research.query()` and gets a ranked consensus from 8 parallel
sources.

| Tool | Speed | Sources | Use when |
|---|---|---|---|
| `quick(question)` | ~3s | web + stackoverflow | fast sanity check |
| `query(question, error_text=None)` | ~5s | 5 web + diagnostics + memory | unknown error, multi-source research |
| `deep(question, error_text=None)` | ~8s | 8 web + diagnostics + memory | critical, 3+ sources must agree |

### How it works

```python
# Instead of 5 sequential calls:
search_web(q)        # 2s
search_stackover(q)  # 2s
classify_error(e)    # 1s
search_nodes(q)      # 0.5s
mdn(q)               # 2s
# Total: 7.5s

# Make 1 call:
research.query(q, error_text=e)
# Runs all 5 in parallel via asyncio.gather
# Total: 2s (max of all, not sum)
# Returns: ranked + cross-checked consensus
```

### Cross-check verdict

The output includes a `─── CROSS-CHECK ───` block with explicit signal:
- ✅ Diagnostics classified: ... + Memory returned N matching entities
- ⚠️ Diagnostics: UNKNOWN error type. Web sources should be authoritative.
- ⚠️ No sources returned content. Refine query and retry.

If 3+ sources agree on a fix, confidence is high. If sources conflict,
the conflict is surfaced to the user.

### Server instructions also enable parallel batching

The 4 core servers (`autofix`, `diagnostics`, `memory`, `think`) now include
instructions telling the model to call them **in parallel** within a single
tool batch. The MCP protocol supports parallel tool calls natively — the
model just needs to be told to use them.

As of 2026-06-06:
- `autofix` and `diagnostics` — **MANDATORY** parallel orchestration on UNKNOWN errors
- `memory` — **MANDATORY** parallel cross-check on error response (3-way: memory + diagnostics + research)
- `think` — **LAG DETECTION**: pass `lag_ms=<ms>`; if `> 10s` without progress, tool demands a parallel web search batch

```json
// Bad: sequential (slow)
result1 = autofix_run(cmd)
result2 = classify_error(err)
result3 = search_nodes(q)

// Good: parallel (one round-trip)
parallel([
  autofix_run(cmd),
  classify_error(err),
  search_nodes(q),
  research.query(q, err)
])

// Good: lag-triggered parallel web search (think > 10s without progress)
parallel([
  think(reasoning="searching for <error>", lag_ms=0),
  web.search_web("<error> 2025 fix"),
  web.search_stackoverflow("<error>"),
])
```

---

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium
python -m pytest tests/ -v    # 175 tests (164 passed + 11 skipped), ~23 seconds (incl. 11 bifrost integration + 7 perf benchmark tests)
```

### Auto-load in every OpenCode session

`verify_setup.py` ensures MCPKU stays registered in the global
`~/.config/opencode/opencode.jsonc` config so it auto-loads in **every
session, every directory, every model** — now and after future opencode
upgrades.

```bash
python verify_setup.py check     # verify current setup (17/17 registered?)
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
    "autofix":    { "type": "local", "command": ["python", "E:/MCPKU/mcp_autofix.py"],    "enabled": true },
    "context7":   { "type": "local", "command": ["npx", "-y", "@upstash/context7-mcp"],    "enabled": true },
    "research":   { "type": "local", "command": ["python", "E:/MCPKU/mcp_research.py"],   "enabled": true }
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
    "autofix":    { "command": "python", "args": ["E:/MCPKU/mcp_autofix.py"] },
    "context7":   { "command": "npx",   "args": ["-y", "@upstash/context7-mcp"] },
    "research":   { "command": "python", "args": ["E:/MCPKU/mcp_research.py"] }
  }
}
```

### Cursor / others

Same pattern — register each `mcp_*.py` as a stdio command. Trim the list to
whatever you need.

---

## Lock with approval — model must ask before editing MCPKU

`opencode.jsonc` ships with a 23-rule `permission` block that gates mutations
on `E:\MCPKU`. The model (and any subagent) can **read** anything freely, but
mutating tools must request approval first.

### What requires approval (path inside `E:\MCPKU`)

| Layer | Tool | Action |
|-------|------|--------|
| Built-in | `edit`, `write` | `ask` — opencode prompts you before running |
| `mcp_filesystem` | `write_file`, `append_file`, `edit_file`, `create_file`, `create_directory`, `move_file`, `delete_file`, `copy_file` | `ask` per file operation |
| `mcp_bash` | `run_command` | `ask` only when command string contains `E:/MCPKU` or `E:\MCPKU`; non-MCPKU commands pass through |
| `mcp_git` | `commit`, `add`, `checkout`, `reset`, `stash`, `merge`, `rebase`, `create_branch`, `tag`, `clone` | `ask` per git operation |
| `mcp_autofix` | `run`, `save_error` | `deny` — auto-execute by design, would defeat the tool to ask |

### What still works inside `E:\MCPKU` without prompts

- All **read** tools (`read_file`, `grep_files`, `search_files`, `list_directory`)
- Git **read-only** (`status`, `log`, `diff`, `show`, `blame`, `branch list`)
- Non-file MCPs (`context7`, `github`, `redis`, `postgres`, `sqlite`, `web`, `time`, `memory`, `think`, `diagnostics`, `research`)
- `mcp_bash` commands that do not touch `E:\MCPKU` (e.g. `ls`, `pytest`, `pip install`)

### How the prompt looks

When the model wants to mutate, opencode shows a confirmation like:

```
[mcp_filesystem] write_file path=E:/MCPKU/mcp_x.py
Allow? (y/n/always):
```

Answer `y` once for that call, or `always` to whitelist that exact tool/path
pattern for the rest of the session.

### Active in two scopes

The same `permission` block lives in:

- `E:\MCPKU\opencode.jsonc` — project-level (active when opencode CWD is `E:\MCPKU`)
- `~/.config/opencode/opencode.jsonc` — user-level (active from any directory)

Precedence: project > user > system, so the rule is always loaded.

### Tighter lock (deny instead of ask)

Change any `"ask"` to `"deny"` in the `permission` block. Useful when you want
MCPKU truly read-only (e.g. for benchmarks). Restart opencode after editing.

```jsonc
"edit": { "*": "allow", "E:/MCPKU/**": "deny", "E:\\MCPKU\\**": "deny" }
```

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
    │                           └── ... (15 more — see table below)
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

**175 tests** across 17 server modules (164 passed + 11 skipped). Pure unit
tests with no network, DB, or browser dependency. Runs in ~23 seconds.

| Module | Tests | What's covered |
|---|---|---|
| `test_diagnostics.py` | 39 | Error classification, traceback parsing (Python/Node/Rust), language detection, history |
| `test_bash.py` | 15 | Command allowlist, argument denylist, git ACL, injection blocking |
| `test_autofix.py` | 29 | Fix handlers, module extraction, async run loop with mocked shell |
| `test_sqlite.py` | 13 | Identifier validation, CRUD operations |
| `test_vector.py` | 9 | Fallback embeddings, collection name sanitization |
| `test_postgres.py` | 4 | Retry with exponential backoff |
| `test_think.py` | 10 | Per-session chain-of-thought + **stuck-pattern detector** (triggers websearch demand after 2 retry thoughts) |
| `test_verify_setup.py` | 10 | JSONC comment stripping, server path validation, expected server count, dispatcher |
| `test_autofallback.py` | manual | Knowledge-graph smoke test (run directly: `python tests/test_autofallback.py`) |
| `test_*` (6 more) | 23 | Git flag protection, memory persistence, timezone, HTML parsing, filesystem paths, Redis flush tokens |

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
| `ERROR_KB_DIR` | `autofix` | `<cwd>/error_kb/` | Force global KB dir (overrides per-project CWD resolution) |
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
| **MCPKU Runtime** | The orchestration layer of 17 coordinated servers |
| **Autonomous Debugging Engine** | The diagnostics + autofix pipeline that closes the debug loop |
| **Closed-loop debugging** | Run → detect → fix → retry → commit without human intervention |
| **Fix strategy** | A handler function that maps an error type to an executable fix command |
| **AI Runtime** | Infrastructure that lets AI models interact with system resources through MCP |

---

## Research Protocol

Agar agen selalu memberikan jawaban akurat dan mutakhir, berikut adalah protokol kerja yang wajib diikuti:

1. **Analisis Durasi:** Jika proses penalaran internal (*thinking*) membutuhkan waktu lebih dari 10 detik atau jika penalaran mandiri dirasa tidak cukup untuk memberikan jawaban yang valid, segera beralih ke alat riset.
2. **Penggunaan Alat:** Gunakan `mcp_web.py`, `WebSearch`, atau `deep-research` untuk mendapatkan data terbaru.
3. **Verifikasi & Referensi:** Setiap klaim atau data yang diambil dari internet wajib menyertakan sumber (URL) yang valid.
4. **Prioritas:** Prioritaskan penggunaan alat riset jika konteks pertanyaan membutuhkan data yang ada di internet (seperti dokumentasi API terbaru, berita terkini, atau riset teknis).

Instruksi ini berlaku untuk seluruh sesi pengembangan di repositori E:\MCPKU.

---

## License

MIT — see [LICENSE](LICENSE).
