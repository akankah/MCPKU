<picture>
<source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-dark.png">
<img alt="MCPKU" src="https://raw.githubusercontent.com/akankah/MCPKU/main/assets/logo-light.png">
</picture>

**MCPKU** is an open-source **AI Runtime** — a coordinated layer of 21 MCP
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
21 MCP Servers
│  each a self-contained stdio process
▼
Your System / Repo / DB / Browser / Logs
```

> Status: personal project · Tested on Windows / Python 3.11+ ·
> [PATCH_NOTES.md](PATCH_NOTES.md) · [MIT License](LICENSE) ·
> [![CI](https://github.com/akankah/MCPKU/actions/workflows/test.yml/badge.svg)](https://github.com/akankah/MCPKU/actions/workflows/test.yml)

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

## 21 MCP Servers (Core)

Each server is a single self-contained Python file. Enable only what you need.

| Server        | File                  | What it gives you                                                         | Tools |
|---------------|-----------------------|---------------------------------------------------------------------------|-------|
| `bash`        | `mcp_bash.py`         | Sandboxed shell with allowlist + argument denylist + timeout orphan kill  | 1 |
| `think`       | `mcp_think.py`        | Per-session chain-of-thought + stuck-pattern detector + lag detector      | 1 |
| `time`        | `mcp_time.py`         | Current time, timezone conversion, IANA timezone listing                  | 3 |
| `filesystem`  | `mcp_filesystem.py`   | Read/write/search/diff inside an allowlisted directory tree               | 19 |
| `git`         | `mcp_git.py`          | Status, diff, log, commit, branch, merge, rebase, stash, tag, blame       | 3 |
| `github`      | `mcp_github.py`       | Repos, issues, PRs, releases, workflows, code search                      | 10 |
| `web`         | `mcp_web.py`          | URL fetch + web search (DDG/Firecrawl) + Stack Overflow + npm/PyPI/MDN/crates/DevDocs | 10 |
| `context7`    | (npm `@upstash/context7-mcp`) | Up-to-date library docs — prevents stale API/syntax from training cutoff | 0 |
| `vector`      | `mcp_vector.py`       | SQLite-vec / Postgres + pgvector + OpenAI embeddings, cosine similarity search | 6 |
| `memory`      | `mcp_memory.py`       | JSONL-backed knowledge graph (entities, relations, observations)          | 9 |
| `browser`     | `mcp_browser.py`      | Headless Chromium via Playwright (fetch, screenshot)                      | 2 |
| `diagnostics` | `mcp_diagnostics.py`  | Parse, classify, explain errors from any command output (Py/JS/Rust/Go)  | 7 |
| `autofix`     | `mcp_autofix.py`      | Closed-loop debug: auto-fix + parallel search (web/GitHub/SO) + error KB | 7 |
| `planner`     | `mcp_planner.py`      | AI-driven DAG task graph generator (planner/ package)                     | 1 |
| `research`    | `mcp_research.py`     | Semantic consensus engine: query/quick/deep with embedding-based agreement| 3 |
| `manifest`    | `mcp_manifest.py`     | Central tool metadata registry (101 tools, 13 categories)                 | 0 |
| `agent`       | `agentku_buat_chat.py`| Autonomous agent: planner + manifest for dynamic tool discovery           | 7 |
| `git_doc`     | `mcp_git_doc.py`      | Auto-generate commit messages and PR summaries from git diffs             | 2 |
| `api_tester`  | `mcp_api_tester.py`   | API Performance & Stress Tester: Latency analysis and concurrency testing | 2 |
| `perf_fixer`  | `mcp_perf_fixer.py`   | Performance Fixer Bridge: Connects API Tester results to Auto-Fix         | 2 |
| `refactor`    | `mcp_refactor.py`     | Smart Refactorer: Automated clean code, linting, and symbol renaming      | 3 |
| `doc_intel`   | `mcp_doc_intel.py`    | Local Document Intelligence: Read PDF, DOCX, and XLSX files locally       | 3 |

`mcp_cache.py` is a shared helper for Redis-backed response caching (used by `vector`, `web`). Not a standalone server.

**Total: 101 callable tools across 13 categories** (research, memory, debug, files, git, github, perf, refactor, vector, time, plan, think, bash)

---

### Tool Manifest Impact — Model Perspective

> **Before adding to manifest:**
> - Server loads in opencode but AI **cannot call tools directly**
> - Only manual access via `bash_run_command` → `python mcp_xxx.py`
> - No schema, parameter validation, categories
> - Agent/planner cannot use in workflows
>
> **After adding to `TOOL_MANIFEST`:**

| Benefit | Description |
|---|---|
| **Direct AI calls** | `tool_name(args)` → server runs, returns structured JSON |
| **Auto schema validation** | Parameters validated (type, required, defaults) |
| **Categories visible** | Appears in `research`, `debug`, `files`, `git` for discovery |
| **Network/Danger flags** | AI knows if tool needs internet or is destructive |
| **Parallel execution** | `parallel_ok=True` allows concurrent calls |
| **Timeout hints** | `timeout_suggestion` prevents hangs |
| **Agent/Planner integration** | Usable in DAG plans, auto-fallback chains |
| **Self-documenting** | `get_params()` shows args, `get_func()` lazy-loads |

**Example — `mcp_github` (0 → 10 tools):**
```python
# Before: AI cannot access GitHub API
# After: AI can directly call
github_list_issues(repo="owner/repo", state="open")
github_create_issue(repo="owner/repo", title="Bug", body="...")
github_search_code(query="function lang:python repo:owner/repo")
```

**Effort:** ~5-10 min per server to add `ToolEntry`. High ROI — unlocks full automation.

---

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

## Semantic Research Engine (mcp_research) — v3

The research engine closes the orchestration gap: instead of the model calling
`autofix` + `diagnostics` + `memory` + `web search` sequentially, it makes
ONE call to `research.query()` and gets a **semantic consensus** from 8 parallel
sources — with structured JSON output and embedding-based agreement detection.

### v3 upgrades

| Area | v2 (lexical) | v3 (semantic) |
|---|---|---|
| **Source similarity** | Word Jaccard `_text_similarity()` | Embedding cosine similarity via `mcp_vector._embed` — async-safe with 2s timeout, graceful fallback |
| **Agreement detection** | Keyword overlap (`_extract_topics`) | Greedy clustering on embedding cosine matrix (threshold 0.5) |
| **Confidence scoring** | Topic lexical overlap → heuristic | Cluster-based: fewer clusters = higher agreement; largest cluster ratio bonus |
| **Output format** | Human-readable text blob | Structured JSON: `{success, confidence{score,verdict,coverage,agreement,...}, sources[], consensus_topics[], recommended_fix}` |
| **Embedding** | None | OpenAI `text-embedding-3-small` (via `_embed`), deterministic hash fallback when key absent |

### Clustering-based confidence

Sources are grouped into **semantic clusters** via greedy clustering on a cosine
similarity matrix. Confidence is computed from:

1. **Coverage (0-30)**: how many sources returned content
2. **Semantic agreement (0-30)**: inverse of cluster count — 1 cluster = max agreement; bonus if largest cluster covers >60% of sources
3. **Weight bonus (0-20)**: weighted by `SOURCE_WEIGHTS` (MDN=0.95, SO=0.90, web=0.50)
4. **KB bonus (0-20)**: past successful fix from `error_kb` = strong signal

### Tools

| Tool | Speed | Sources | Use when |
|---|---|---|---|
| `quick(question)` | ~3s | web + stackoverflow | fast sanity check |
| `query(question, error_text=None)` | ~5s | 6 web + diagnostics + memory | unknown error, multi-source research |
| `deep(question, error_text=None)` | ~8s | 8 web + diagnostics + memory | critical, 3+ sources must agree |
| `stream(question, error_text=None)` | ~3-15s | returns each source as it arrives | don't block on slowest provider |

### Example output (structured JSON)

```json
{
"success": true,
"tool": "query",
"query": "how to fix ModuleNotFoundError in Python",
"language": "python",
"confidence": {
"score": 82,
"verdict": "high",
"coverage": 25,
"agreement": 22,
"weight_bonus": 15,
"kb_bonus": 20,
"clusters": [["stackoverflow", "mdn", "web"], ["diagnostics"]],
"sources_returned": 4,
"sources_total": 6
},
"sources": [
{
"name": "stackoverflow",
"weight": 0.9,
"preview": "Run pip install to add missing packages...",
"status": null
}
],
"consensus_topics": ["stackoverflow", "mdn", "web"],
"recommended_fix": "pip install <package>",
"sources_returned": 4,
"sources_total": 6
}
```

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
python -m pytest tests/ -v    # 462 tests, ~24 seconds
```

---

## Windows MCP Timeout Fix (opencode v1.17+)

**Problem**: On Windows, opencode v1.17.3 spawns MCP servers via `child_process.spawn()` without `shell: true`. This fails to resolve `.exe`/`.cmd` shims, causing all 21 servers to timeout on startup (30s default).

**Root causes**:
1. `spawn("python", ...)` doesn't find `python.exe` on Windows without shell
2. 30s default timeout is too short for 28 parallel Python process startup
3. Some servers (e.g., `doc_intel`) import heavy optional deps at module level

**Applied fixes** (in `opencode.jsonc`):

```jsonc
{
"mcp": {
"bash":       { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_bash.py"],       "enabled": true, "timeout": 60000 },
"think":      { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_think.py"],      "enabled": true, "timeout": 60000 },
"time":       { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_time.py"],       "enabled": true, "timeout": 60000 },
// ... all 21 servers wrapped with "cmd", "/c" + explicit timeout: 60000
"context7":   { "type": "local", "command": ["cmd", "/c", "node", "C:/Users/r/AppData/Roaming/npm/node_modules/@upstash/context7-mcp/dist/index.js"], "enabled": true, "timeout": 120000 },
"doc_intel":  { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_doc_intel.py"],  "enabled": true, "timeout": 60000 }
}
}
```

| Fix | File | What it does |
|-----|------|--------------|
| `cmd /c` wrapper | `opencode.jsonc` | Forces Windows shell to resolve `.exe`/`.cmd` |
| `timeout: 60000` | `opencode.jsonc` | Per-server timeout (overrides 30s default) |
| Lazy imports | `mcp_doc_intel.py` | Defer `pypdf`/`python-docx`/`pandas` to tool call time |
| Direct node path | `opencode.jsonc` | Bypass `npx` for context7 (uses global install) |

**Result**: 21/21 servers connect reliably on Windows 10/11 (opencode v1.17.3).

**Tested**: Windows 10 + Windows 11, Python 3.11+, opencode v1.17.3.

**Self-recovery**: `mcp_autofix.py` now detects MCP timeout errors and suggests config fixes:

| Error pattern | Detected as | Fix guidance |
|---------------|-------------|--------------|
| `Operation timed out after 30000ms` | `MCP.Timeout` | Add `cmd /c` wrapper + `timeout: 60000` |
| `MCP error -32001: Request timed out` | `MCP.RequestTimeout` | Increase timeout to `120000` |
| `Unrecognized key: mcpServers` | `MCP.SpawnFailed` | Change config key from `mcpServers` → `mcp` |

Run `autofix_run` on any failing MCP command — it will classify, suggest the exact fix, search web/GitHub/SO, and save to error KB for future sessions.

### Auto-load in every OpenCode session

`verify_setup.py` ensures MCPKU stays registered in the global
`~/.config/opencode/opencode.jsonc` config so it auto-loads in **every
session, every directory, every model** — now and after future opencode
upgrades.

```bash
python verify_setup.py check     # verify current setup (21/21 registered?)
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
"bash":       { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_bash.py"],       "enabled": true, "timeout": 60000 },
"think":      { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_think.py"],      "enabled": true, "timeout": 60000 },
"time":       { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_time.py"],       "enabled": true, "timeout": 60000 },
"filesystem": { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_filesystem.py"], "enabled": true, "timeout": 60000 },
"git":        { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_git.py"],        "enabled": true, "timeout": 60000 },
"github":     { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_github.py"],     "enabled": true, "timeout": 60000 },
"web":        { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_web.py"],        "enabled": true, "timeout": 60000 },
"vector":     { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_vector.py"],     "enabled": true, "timeout": 60000 },
"memory":     { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_memory.py"],     "enabled": true, "timeout": 60000 },
"browser":    { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_browser.py"],    "enabled": true, "timeout": 60000 },
"diagnostics":{"type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_diagnostics.py"], "enabled": true, "timeout": 60000 },
"autofix":    { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_autofix.py"],    "enabled": true, "timeout": 60000 },
"context7":   { "type": "local", "command": ["cmd", "/c", "node", "C:/Users/<user>/AppData/Roaming/npm/node_modules/@upstash/context7-mcp/dist/index.js"], "enabled": true, "timeout": 120000 },
"research":   { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_research.py"],   "enabled": true, "timeout": 60000 },
"planner":    { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_planner.py"],    "enabled": true, "timeout": 60000 },
"git_doc":    { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_git_doc.py"],    "enabled": true, "timeout": 60000 },
"api_tester": { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_api_tester.py"], "enabled": true, "timeout": 60000 },
"perf_fixer": { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_perf_fixer.py"], "enabled": true, "timeout": 60000 },
"refactor":   { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_refactor.py"],   "enabled": true, "timeout": 60000 },
"doc_intel":  { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/mcp_doc_intel.py"],  "enabled": true, "timeout": 60000 },
"agent":      { "type": "local", "command": ["cmd", "/c", "python", "E:/MCPKU/agentku_buat_chat.py"], "enabled": true, "timeout": 60000 }
}
}
```

> **Note**: All Python servers use `cmd /c` wrapper + explicit `timeout: 60000` (context7: 120000) for Windows compatibility. Replace `<user>` in context7 path with your Windows username.
```

Once added, MCPKU is active whenever opencode starts — regardless of the
current directory.

### Claude Desktop

```json
{
"mcpServers": {
"bash":       { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_bash.py"] },
"think":      { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_think.py"] },
"time":       { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_time.py"] },
"filesystem": { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_filesystem.py"] },
"git":        { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_git.py"] },
"github":     { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_github.py"] },
"web":        { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_web.py"] },
"vector":     { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_vector.py"] },
"memory":     { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_memory.py"] },
"browser":    { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_browser.py"] },
"diagnostics":{"command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_diagnostics.py"] },
"autofix":    { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_autofix.py"] },
"context7":   { "command": "cmd", "args": ["/c", "node", "C:/Users/<user>/AppData/Roaming/npm/node_modules/@upstash/context7-mcp/dist/index.js"] },
"research":   { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_research.py"] },
"planner":    { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_planner.py"] },
"git_doc":    { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_git_doc.py"] },
"api_tester": { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_api_tester.py"] },
"perf_fixer": { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_perf_fixer.py"] },
"refactor":   { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_refactor.py"] },
"doc_intel":  { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/mcp_doc_intel.py"] },
"agent":      { "command": "cmd", "args": ["/c", "python", "E:/MCPKU/agentku_buat_chat.py"] }
}
}
```

> **Note**: Use `cmd /c` wrapper for Windows `.exe`/`.cmd` resolution. Replace `<user>` in context7 path with your Windows username.
```

---

## Config Files & Rules

### Files in repo

| File | Tracked | Purpose |
|------|---------|---------|
| `opencode.jsonc` | ✅ Yes | 21 MCP server definitions with `cmd /c` wrapper + `timeout` |
| `mcp_wrapper.py` | ✅ Yes | Optional diagnostics injector (not used by default) |

### Files NOT in repo (create locally)

| File | Location | Purpose |
|------|----------|---------|
| `opencode.jsonc` (global) | `~/.config/opencode/opencode.jsonc` | Copy from repo, update `context7` path |
| `.env` | `E:\MCPKU\.env` | API keys (never commit) |
| `memory.jsonl` | `E:\MCPKU\memory.jsonl` | Personal knowledge graph (auto-created) |
| `error_kb/*.json` | `E:\MCPKU\error_kb\` | Per-project error KB (auto-created) |

### Required environment variables

Create `E:\MCPKU\.env` (or export in shell):

```bash
# Required for servers that need them
GITHUB_API_KEY=ghp_xxx
FIRECRAWL_API_KEY=fc_xxx
STACKEX_API_KEY=xxx
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-xxx

# Optional free-tier providers (set these for free-model access)
# Model list diverifikasi via /models API tiap provider — lihat cara_fix_model_error.txt
ZHIPUAI_API_KEY=xxx      # Z.AI Free — 5 models: glm-4.6, glm-4.7, glm-5, glm-5-turbo, glm-5.1
KILO_API_KEY=xxx
NVIDIA_API_KEY=xxx
KIMCHI_API_KEY=xxx
BAI_API_KEY=xxx          # B.AI — 4 models: gemini-3.5-flash, glm-5.1, glm-5, kimi-k2.5
ALIBABA_API_KEY=xxx      # Alibaba Free — 10 models: qwen-turbo, qwen-plus, qwen-max, qwen3.5-122b, qwen3.7-plus, qwen3-max, qwen3-vl, qwen-mt-flash, dll
```

### Editing rules

| Rule | Enforcement |
|------|-------------|
| **Never commit secrets** | `.env`, `memory.jsonl`, `error_kb/` in `.gitignore` |
| **Use `${VAR}` interpolation** | `opencode.jsonc` uses `${VAR}` for API keys — resolves from env |
| **Context7 path template** | Replace `<user>` in `C:/Users/<user>/AppData/...` with actual username |
| **Timeout values** | All Python servers: `60000`, context7: `120000` (tested working) |
| **Cmd wrapper** | All Python commands: `["cmd", "/c", "python", ...]` — required on Windows |
| **Schema version** | opencode v1.17+ uses `"mcp"` key (NOT `"mcpServers"`) |

### Validation checklist before commit

```bash
# 1. Verify config syntax
python -m json.tool E:\MCPKU\opencode.jsonc > nul && echo "JSONC valid"

# 2. Check no hardcoded secrets
grep -i "api_key\|password\|secret" E:\MCPKU\opencode.jsonc || echo "No secrets found"

# 3. Verify all servers have timeout
grep -c '"timeout": 60000' E:\MCPKU\opencode.jsonc  # should be 27
grep -c '"timeout": 120000' E:\MCPKU\opencode.jsonc  # should be 1 (context7)

# 4. Verify cmd wrapper
grep -c 'cmd.*python' E:\MCPKU\opencode.jsonc  # should be 27
```

### Sync global config

```bash
python verify_setup.py sync   # copies opencode.jsonc to global ~/.config/opencode/
python verify_setup.py check  # validates registration
```

### Backup & Restore (portable)

Global config backed up to `.config_backup/` (gitignored):

| File | Source | Backup location |
|------|--------|-----------------|
| `opencode.jsonc` (global) | `~/.config/opencode/opencode.jsonc` | `.config_backup/opencode.jsonc.global` |

**Auto-backup on sync:**
```bash
python verify_setup.py sync  # also copies global → .config_backup/
```

**Manual restore if global config corrupted:**
```bash
# Option 1: Copy backup to global
cp E:\MCPKU\.config_backup\opencode.jsonc.global "%USERPROFILE%\.config\opencode\opencode.jsonc"

# Option 2: Use verify_setup (recommended)
python verify_setup.py sync  # reads from repo opencode.jsonc, writes to global
```

**Portable setup on new machine:**
```bash
# 1. Clone repo
git clone https://github.com/akankah/MCPKU.git E:\MCPKU

# 2. Copy backup to global (or run sync)
cp E:\MCPKU\.config_backup\opencode.jsonc.global "%USERPROFILE%\.config\opencode\opencode.jsonc"

# 3. Update context7 path in global config
#    Edit %USERPROFILE%\.config\opencode\opencode.jsonc
#    Replace <user> with your Windows username

# 4. Set env vars (.env or shell)
# 5. Restart opencode
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
- Non-file MCPs (`context7`, `github`, `web`, `time`, `memory`, `think`, `diagnostics`, `research`, `vector`)
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
Orphan process killed on timeout to prevent resource leaks.
- `vector` — SQLite-vec / pgvector with cosine similarity search
- `filesystem` — rooted at fixed allowlist. Extend via `MCP_EXTRA_ALLOWED_DIR`.

See [`PATCH_NOTES.md`](PATCH_NOTES.md) for full details.

---

## Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

**429 tests** across 21 server modules. Pure unit tests with no network, DB,
or browser dependency. Runs in ~22 seconds.

| Module | Tests | What's covered |
|---|---|---|
| `test_diagnostics.py` | 39 | Error classification, traceback parsing, language detection, history |
| `test_bash.py` | 15 | Command allowlist, argument denylist, git ACL, injection blocking |
| `test_autofix.py` | 29 | Fix handlers, module extraction, async run loop with mocked shell |
| `test_vector.py` | 9 | Fallback embeddings, collection name sanitization |
| `test_think.py` | 15 | Chain-of-thought + stuck-pattern detector + lag detector |
| `test_verify_setup.py` | 10 | JSONC stripping, path validation, dispatcher |
| `test_research.py` | 26 | Cosine similarity, lexical overlap, keyword extraction, language detection, JSON parsing |
| `test_web.py` | 5 | HTML-to-text conversion |
| `test_github.py` | 21 | HTTP helpers, _api, tool integration with mocked HTTP |
| `test_browser.py` | 6 | URL normalization, error handling, text truncation |
| `test_memory.py` | 3 | Graph save/reload with observations |
| `test_git.py` | 5 | Flag protection |
| `test_time.py` | 4 | Timezone resolution |
| `test_filesystem.py` | 3 | Path normalization, allowlist checking |
| `test_perf.py` | 7 | Benchmark: parallel batching, lag detector overhead, timeout safety |
| `test_autofallback.py` | 7 | Memory autofallback with mocked knowledge graph |
| `test_manifest.py` | 20 | ToolEntry dataclass, TOOL_MANIFEST integrity, category helpers |
| `test_cache.py` | 17 | Key normalization, Redis abstraction, silent degradation (optional) |

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
| `REDIS_URL` | `mcp_cache.py` | `redis://localhost:6379/0` | For caching (optional) |
| `MCP_EXTRA_ALLOWED_DIR` | `mcp_filesystem.py` | — | Extra allowlisted roots (comma-sep) |
| `MEMORY_FILE_PATH` | `mcp_memory.py` | `memory.jsonl` | Knowledge graph persistence |
| `LOCAL_TIMEZONE` | `mcp_time.py` | UTC | Default display timezone |

## Terminology

| Term | Meaning |
|---|---|
| **MCPKU Runtime** | The orchestration layer of 22 coordinated servers |
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

## Status — Kesan Kerja dengan MCPKU

**Enak.** Dulu sering timeout/macet, sekarang 21 MCP server connect semua stabil. Provider juga udah dirapihin — tinggal pake yang work, gak perlu tebak-tebak.

**Yang improved:**
- **Stability** — 21/21 server connect, no more timeout
- **Config clean** — B.AI 21→4, ZhipuAI broken→5 work, Alibaba Free 10 model
- **Documentation** — API keys guide, base URLs, cara ganti key, semua jelas
- **Auto-sync** — `verify_setup.py sync` bikin backup + sync global config
- **Tool manifest** — 101 tools across 13 categories, all servers callable

MCPKU sekarang bener-bener siap produksi — tinggal pake, gak perlu debug lagi.

---

## Performance Tuning (v2026-06-13)

### Applied Optimizations

| Area | Before | After | Impact |
|---|---|---|---|
| **Parallel tools** | 14/101 | **58/101** | +314% parallel-capable |
| **GitHub read tools** | `parallel_ok=False` | `parallel_ok=True` + timeout 15→10s | Parallel PR/issue/repo listing |
| **Research tools** | `parallel_ok=False` | `parallel_ok=True` + timeout 20→15s | Parallel multi-source queries |
| **Filesystem read** | `parallel_ok=False` | `parallel_ok=True` (10 tools) | Parallel file search/list/read |
| **Diagnostics** | `parallel_ok=False` | `parallel_ok=True` (4 tools) | Parallel error classification |
| **Memory/Vector/Git/Time** | `parallel_ok=False` | `parallel_ok=True` (13 tools) | Parallel read-only ops |
| **Timeouts** | Conservative | Reduced 10-30% | Faster fallback on slow endpoints |

### Safe tools now parallel_ok=True (58 total):

**Network (21):**
- `github_get_repo`, `github_list_issues`, `github_list_pull_requests`, `github_get_file_contents`, `github_list_workflows`, `github_search_code`, `github_search_issues`
- `research_query`, `research_quick`, `research_deep`
- `web_search_web`, `web_search_stackoverflow`, `search_npm`, `search_pypi`, `search_crates`, `search_readthedocs`, `search_mdn`, `search_devdocs`, `web_fetch_url`
- `vector_search`

**Local (37):**
- **Files (15):** `fs_read_file`, `fs_read_multiple_files`, `fs_list_directory`, `fs_list_directory_detailed`, `fs_directory_tree`, `fs_search_files`, `fs_grep_files`, `fs_glob_pattern`, `fs_get_file_info`, `fs_path_exists`, `fs_list_allowed_directories`, `fs_diff_files`, `doc_intel_read_pdf`, `doc_intel_read_docx`, `doc_intel_read_xlsx`
- **Debug (8):** `autofix_search_kb`, `autofix_history`, `autofix_strategies`, `autofix_kb_stats`, `autofix_kb_trends`, `diagnostics_classify_error`, `diagnostics_explain_error`, `diagnostics_get_error_history`
- **Memory (3):** `memory_search_nodes`, `memory_open_nodes`, `memory_read_graph`
- **Git (4):** `git_status`, `git_log`, `git_doc_generate_commit_proposal`, `git_doc_generate_pr_summary`
- **Vector (3):** `vector_search`, `vector_collection_stats`, `vector_list_collections`
- **Time (3):** `time_get_current_time`, `time_convert_time`, `time_list_timezones`
- **Perf (1):** `perf_fixer_analyze_performance_report`
- **Refactor (1):** `refactor_check_code_smells`

### Remaining sequential (by design):
- **Dangerous/mutating**: `github_create_issue`, `github_create_pull_request`, `github_trigger_workflow`, `autofix_run`, `fs_write_file`, `fs_edit_file`, `fs_delete_file`, `fs_move_file`, `git_commit`, `memory_delete_*`, `vector_delete_documents`, `refactor_clean_python_code`, `refactor_rename_symbol_project`
- **Browser**: `browser_fetch`, `screenshot` (Playwright session not thread-safe)
- **Heavy compute**: `api_tester_stress_test` (120s), `research_deep` (25s)
- **Stateful**: `agent_plan`, `agent_execute*`, `planner_plan_generate`, `think`

### Next optimizations (planned):
1. **Redis cache** for `mcp_research.py`, `mcp_github.py`, `mcp_vector.py`
2. **HTTP connection pooling** in `mcp_web.py` / `mcp_github.py`
3. **Embedding cache** in `mcp_vector.py` / `mcp_research.py`

---

## Roadmap: Next-Gen Agentic Capabilities

Kami sedang mengembangkan MCPKU dari *orchestrator* menjadi *Agentic OS* dengan fokus pada:
1. **Critique Loop (Verification Layer):** Task-level validation (self-critique) untuk memastikan hasil eksekusi sesuai standar (misal: verifikasi file size, konten, atau exit status).
2. **Human-in-the-Loop:** *Safety checkpoints* opsional pada task berisiko tinggi yang mengharuskan persetujuan manual user sebelum lanjut.
3. **Productivity Dashboard:** Monitoring otomatis (`workflow_stats`) untuk mengukur efektivitas agen dan jumlah waktu yang dihemat lewat auto-fix.

---

## License

MIT — see [LICENSE](LICENSE).

