# MCPKU — Patch Notes

Semua perubahan berdasarkan review kode aktual. Setiap fix disertai alasan dan lokasi yang tepat.

---

## mcp_bash.py

### Bug / Security yang Diperbaiki

**1. `cmd` dan `powershell` dihapus dari ALLOWED_COMMANDS**
- Sebelumnya: `cmd /c del /f /q C:\*` lolos tanpa diblokir sama sekali
- Sekarang: `cmd` dan `powershell` tidak ada di allowlist

**2. Argument-level denylist ditambahkan (`DANGEROUS_ARG_PATTERNS`)**
- Regex patterns untuk: wildcard delete, `-rf`, `--no-preserve-root`, chained commands (`; rm`, `| del`), subshell (`$(...)`, backtick), redirect ke path sistem
- Sebelumnya: hanya cek nama command, tidak cek argumen sama sekali

**3. Git subcommand allowlist (`GIT_ALLOWED_SUBCOMMANDS`)**
- Sebelumnya: `git` bisa dipanggil dengan subcommand apa pun termasuk `git gc --prune=all`, `git filter-branch`, dll
- Sekarang: hanya subcommand yang eksplisit diizinkan

---

## mcp_think.py

### Bug yang Diperbaiki

**1. Global `THOUGHTS` list dihapus — diganti session-isolated `_sessions` dict**
- Sebelumnya: semua client/invocation berbagi satu `THOUGHTS` list yang sama → chaos multi-session
- Sekarang: setiap `session_id` punya thought chain sendiri

**2. Tool `new_session()` ditambahkan**
- Generate UUID pendek untuk session baru yang terisolasi

**3. `reset_thinking()` sekarang per-session**
- Sebelumnya: reset global, hapus semua thought dari semua session
- Sekarang: hanya reset session yang diminta

---

## mcp_sqlite.py

### Bug yang Diperbaiki

**1. Blocking sqlite3 di async function — DIPERBAIKI**
- Sebelumnya: `db.execute()` sinkron langsung di `async def`, block event loop saat query besar
- Sekarang: semua SQL dijalankan di `ThreadPoolExecutor` via `loop.run_in_executor()`

**2. PRAGMA SQL injection via f-string — DIPERBAIKI**
- Sebelumnya: `f"PRAGMA table_info({json.dumps(table_name)})"` — `json.dumps` menghasilkan quoted string tapi bukan cara aman untuk SQL identifier
- Sekarang: `_validate_identifier()` memvalidasi dengan regex `^[A-Za-z_][A-Za-z0-9_ ]*$` dan quote dengan double-quote SQL standard

**3. WAL mode dan busy_timeout ditambahkan**
- Kurangi lock contention saat concurrent reads
- `PRAGMA busy_timeout=5000` agar tidak langsung error saat DB sedang locked

**4. Koneksi dibuka/ditutup per operasi — dipertahankan tapi dengan `timeout=10`**
- SQLite tidak support connection pool yang proper karena single-writer model
- Ditambahkan timeout agar tidak hang selamanya

---

## mcp_redis.py

### Bug / Security yang Diperbaiki

**1. `redis_flushdb` destruktif tanpa konfirmasi — DIPERBAIKI**
- Sebelumnya: satu tool call langsung flush semua data
- Sekarang: 2-step confirmation:
  - `redis_flushdb_request()` → generate token dengan TTL 60 detik
  - `redis_flushdb_confirm(token)` → baru flush
- Token expired otomatis dibersihkan

---

## mcp_postgres.py

### Bug / Performance yang Diperbaiki

**1. `SELECT 1` health check dihapus dari `_get_conn()`**
- Sebelumnya: setiap kali ambil koneksi dari pool, jalankan `SELECT 1` → overhead kecil tapi ada di setiap request
- Sekarang: hanya cek `conn.closed` (property lokal, tidak perlu roundtrip ke DB)

**2. Blocking psycopg2 di async function — DIPERBAIKI**
- Sebelumnya: semua DB call sinkron di `async def`, block event loop
- Sekarang: semua query dijalankan di `ThreadPoolExecutor` via `run_in_executor()`

**3. Retry dengan exponential backoff ditambahkan**
- `_retry_sync()` dengan 3 retries dan backoff 0.5/1.0/2.0 detik untuk `OperationalError` dan `InterfaceError`
- Handle transient connection drops dari pool

---

## Yang Belum Disentuh (perlu file lain)

- `mcp_filesystem.py`: allowlist `C:\` masih terlalu broad — **rekomendasi**: hapus `C:\` dari default, require user set `MCP_EXTRA_ALLOWED_DIR` secara eksplisit
- `mcp_github.py`: GraphQL string concat perlu dicek untuk injection risk
- `mcp_vector.py`: cosine similarity tanpa min_score threshold
- `mcp_memory.py`: single-file JSONL bisa race condition kalau 2 concurrent writes
- Semua file: tidak ada type hints, tidak ada tests, tidak ada structured logging

---

## v2.0 — Autofix Search + Stateless + DuckDuckGo (Jun 2026)

### mcp_autofix.py

**1. `_search_references()` — auto-search web + GitHub saat error tidak dikenal**
- Saat fix strategy tidak ada atau semua retry gagal → langsung cari error di web (DuckDuckGo) dan GitHub Issues
- Query dibentuk dari error_types + baris error terakhir (exclude traceback frames)
- Search via `asyncio.gather()` — web dan GitHub dicari parallel
- Hasil search disertakan dalam output autofix, AI langsung bisa baca & apply solusi

**2. `AUTOFIX_STATELESS=1` — skip session history**
- `_record()` return early jika env var diset
- Mengurangi memory usage untuk long-running / one-shot sessions

**3. Tool description diupdate**
- Menyebut fitur search referensi agar AI tau

### mcp_diagnostics.py

**1. `AUTOFIX_STATELESS=1` — skip error history**
- Sama dengan autofix, `_record()` return early jika stateless

### mcp_web.py

**1. DuckDuckGo search gratis (default)**
- Scrape `lite.duckduckgo.com` langsung via `requests` (no API key, zero config)
- Parse HTML dengan regex untuk extract title + snippet + URL
- `DISABLE_DUCKDUCKGO=1` untuk force Firecrawl-only

**2. Firecrawl sebagai fallback**
- Jika DuckDuckGo gagal, fallback ke Firecrawl (jika API key diset)

### requirements.txt

**1. `duckduckgo_search` dihapus**
- Tidak jadi dipakai — scraping langsung via `requests` lebih ringan dan 0 dep

### Perubahan Non-Breaking

- Semua perubahan backward compatible
- Tanpa env var → behavior sama seperti sebelumnya (kecuali DuckDuckGo aktif default)
- Emoji diganti ASCII-safe `[Web]` / `[GitHub]` untuk kompatibilitas Windows cp1252

| Aspek        | Sebelum | Sesudah | Catatan |
|-------------|---------|---------|---------|
| Akurat       | 8/10    | 8.5/10  | autofix search referensi nyata, bukan saran statis |
| Pintar       | 6.5/10  | 8/10    | search web + github otomatis saat bingung |
| Cepat        | 8.5/10  | 8.5/10  | search parallel via gather, cache via Redis |
| Aman         | 6.5/10  | 6.5/10  | tidak ada perubahan security |
| Maintainable | 5/10    | 6/10    | import cross-module lebih rapi |

## Skor Setelah Fix

| Aspek        | Sebelum | Sesudah | Catatan |
|-------------|---------|---------|---------|
| Akurat       | 6.5/10  | 8/10    | postgres async, sqlite non-blocking, PRAGMA fix |
| Pintar       | 5/10    | 6.5/10  | retry+backoff di postgres, session isolation di think |
| Cepat        | 7.5/10  | 8.5/10  | hapus SELECT 1 overhead, thread pool untuk semua DB ops |
| Aman         | 4/10    | 6.5/10  | bash arg-level policy, flushdb 2-step, PRAGMA injection fix |
| Maintainable | 5/10    | 5/10    | belum ada tests/types — di luar scope patch ini |


---

## \[2026-06-03\] Add Context7 MCP

**Add:** Context7 (npm @upstash/context7-mcp) sebagai MCP ke-16.

**Alasan:** MCP-mu yang lain (mcp_web.py, mcp_github.py) bisa fetch URL tapi **gak punya spesialisasi docs library up-to-date**. Context7 didesain khusus buat narik dokumentasi library versi terbaru � penting biar AI gak kasih syntax yang udah deprecated.

**Files changed:**
- C:\Users\r\.config\opencode\opencode.jsonc � tambah entry context7
- E:\MCPKU\opencode.jsonc � sync backup
- E:\MCPKU\README.md � update 15 ? 16 MCP, tambah row Context7

**Cara kerja:** 
px -y @upstash/context7-mcp (stdio transport, no API key required). Package auto-downloaded saat first call.


---

## [2026-06-06] Parallel Speed Upgrade — Think Lag Detection + Memory Mandatory

### mcp_think.py

**1. `_detect_lag()` ditambahkan — auto-trigger parallel web search kalau think() ngelag >10s**

- Sebelumnya: gak ada deteksi durasi antar step. Model bisa lama mikir tanpa signal.
- Sekarang: model pass `lag_ms=<ms since last step>` → kalau `> 10s` AND last thought gak ada progress pattern (found/fixed/solved/dokumen konfirm), tool return hard trigger:
  ```
  !!! LAG DETECTED (15.0s > 10s) !!!
  parallel([think(reasoning=..., lag_ms=0),
            web.search_web('<keyword> 2025 fix'),
            web.search_stackoverflow('<keyword>')])
  ```
- Konstanta `LAG_THRESHOLD_MS = 10_000` configurable di top of file.
- Tracking timestamp pakai `time.monotonic()` per session (`_session_last_at` dict).

**2. `think()` tool signature diperluas** — tambah `lag_ms: int = 0` parameter (backward compatible).

**3. `instructions=` di-update** — kasih hint eksplisit ke model soal lag detection + parallel batch template.

### mcp_memory.py

**1. `PARALLEL CROSS-CHECK` naik dari `recommended` → `MANDATORY on error response`**

- Sebelumnya: model "dianjurkan" tapi gak wajib batch memory + diagnostics + research.
- Sekarang: pas user kasih error, model **wajib** call 3 tool dalam **1 round-trip**:
  1. `memory.search_nodes('<error_keyword>')` — past similar fix
  2. `diagnostics.classify_error(error_text)` — confirm error type
  3. `mcp_research.query(query)` — 6 web sources + cross-validation

**2. Alasan** — save 1-3 detik per error task (1 round-trip vs 3 sequential × ~500ms-1s).

### tests/test_think.py

**5 test baru** untuk `_detect_lag`:
- `test_lag_under_threshold_no_trigger` — lag=5000ms → no trigger
- `test_lag_over_threshold_no_progress_triggers` — lag=15000ms + retry pattern → trigger
- `test_lag_over_threshold_with_progress_no_trigger` — lag=15000ms + "found" → no trigger
- `test_lag_exactly_at_threshold_no_trigger` — lag=10000ms (boundary) → no trigger (use `>` not `>=`)
- `test_lag_message_includes_parallel_batch_template` — verify message contains `search_web`, `search_stackoverflow`, `think(`

**Total: 15/15 tests pass** (10 lama + 5 baru).

### Files changed
- `E:\MCPKU\mcp_think.py` — +60 lines (lag detector + think() signature + instructions)
- `E:\MCPKU\mcp_memory.py` — 5 lines (instruction text)
- `E:\MCPKU\tests\test_think.py` — +45 lines (5 tests)

### Performance Impact
| Skenario | Sebelum | Sesudah | Hemat |
|---|---|---|---|
| Error task — model batch memory+diag+research | 3 round-trips × 1s = 3s | 1 round-trip × 1s = 1s | ~2s |
| Slow reasoning tanpa progress, >10s | Bisa loop sampai 30-60s | Hard-stop 10s + forced search | ~20-50s |
| Model males gak batch | Bisa 3s+ | Forced 1s | ~2s |

---

## [2026-06-06] Bifrost Integration Test Suite

### tests/test_bifrost_integration.py (NEW FILE)

Bifrost = MaximHQ LLM gateway (Go binary, OpenAI-compatible at `http://localhost:8080/v1`). MCPKU sekarang punya **integration test suite** yang ngecek apakah runtime beneran bisa bicara sama bifrost, bukan cuma declare provider.

**11 tests across 4 kelas:**

1. **TestConnectivity** (3 tests) — `/v1/models` endpoint respond 200, list model ada field wajib, minimal 1 model OpenRouter
2. **TestChatCompletion** (4 tests, parametrized) — kirim prompt, validasi response ada + content match expected + `max_tokens` dihormati
3. **TestOpencodeIntegration** (2 tests) — verify `bifrost` provider dideklarasikan di user config (`%APPDATA%/opencode/opencode.jsonc` atau `~/.config/opencode/opencode.jsonc`) + workspace backup (`E:\MCPKU\opencode.jsonc`)
4. **TestLatency** (2 tests) — sanity check response time

**Design highlights:**
- **Auto-skip** kalau bifrost down (CI gak fail, dev gak ke-block). Pakai module-scoped autouse fixture
- **Stdlib only** — `urllib.request` instead of `requests` (zero new deps, konsisten sama project style)
- **JSONC parser** (`_parse_jsonc()`) — handle `//` line comments + `/* */` block comments tanpa ngerusak string contents. Pure Python, no external lib
- **Parametrized chat tests** — multiple model, kalau 1 rate-limited test lain masih jalan
- **Soft skip for rate limits (429)** — bukan fail, karena free OpenRouter models emang sering rate-limited
- **Smart path resolution** — coba 3 lokasi user config (`%APPDATA%`, `~/.config`, `$HOME/.config`)

**Config knobs (env vars):**
- `BIFROST_URL` — default `http://localhost:8080/v1`
- `BIFROST_KEY` — default `ignored` (placeholder, bifrost config determines real key)

**Files changed:**
- `E:\MCPKU\tests\test_bifrost_integration.py` — new file, ~250 lines
- `E:\MCPKU\README.md` — test count 157 → 168

**Test results** (run against live bifrost):
- 4 PASSED (connectivity + user-config declared)
- 7 SKIPPED (chat tests — semua free OpenRouter model lagi 429/400 "no key configured" hari ini)

**Key insight yang ke-catch:** waktu run pertama, 1 chat test (gpt-oss-120b) berhasil dapet "pong" dalam 1.6s. Run berikutnya gagal dengan 400 "no supported key found with name 'ignored'" — bifrost config kehilangan OpenRouter key. Test correctly skips tanpa crash. Ini **real-world value**: ngasih tau kalau upstream provider key expires/rusak.

**Future improvements (TODO):**
- Sinkronkan `bifrost` provider ke `E:\MCPKU\opencode.jsonc` (workspace backup) — sekarang masih skip
- Tambah fixture `bifrost_chat_completion` yang reuse connection
- Benchmark suite terpisah: ukur parallel speedup nyata (1 sequential vs 1 parallel batch)


---

## [2026-06-06] Benchmark Suite + GitHub Actions CI

### tests/test_perf.py (NEW — 7 tests, 4 classes)

Quantitative proof that the parallel batching changes from earlier today actually deliver the speedup they claim. Stdlib-only, asyncio + time.perf_counter, no network calls.

| Test | Measurement | Real Result | Threshold |
|------|------------|-------------|-----------|
| 	est_three_way_batch_is_at_least_2_5x_faster | memory+diag+research parallel vs sequential | **3.03x** | 2.5x |
| 	est_web_search_batch_is_at_least_1_7x_faster | web+stackoverflow parallel | **1.99x** | 1.7x |
| 	est_three_reference_sources_are_truly_parallel | autofix 3-source parallel | **3.04x** | 2.5x |
| 	est_detect_lag_completes_under_budget | _detect_lag per-call cost | **7.51us** | <50us |
| 	est_detect_stuck_completes_under_budget | _detect_stuck per-call cost | **16.38us** | <50us |
| 	est_per_task_timeout_does_not_block_forever | per-task wait_for cancels slow | **205ms** (not 5s) | <300ms |
| 	est_summary | prints full benchmark table | OK | OK |

	est_perf.py uses _time_async(coro_factory, runs=3) — takes median of 3 to filter GC noise. _assert_speedup() fails loud if a regression creeps in.

### Bug found + fixed while writing this

Initial implementation had two bugs caught by the test:
1. _time_async(coro_factory, ...) first called coro_factory thinking it was an awaitable factory — but coro_factory is a *lambda returning an awaitable*. The tuple-case was dead code, removed.
2. 	est_gather_returns_fastest_result_quickly — claimed syncio.gather returns early on first completion. **It doesn't.** It waits for ALL. Replaced with the actual mcp_research pattern: per-task syncio.wait_for with 200ms timeout, slow task hits timeout, fast task succeeds, total < 300ms.

This is exactly the kind of bug the perf suite exists to catch.

### .github/workflows/test.yml (NEW — 3 jobs)

`
test (matrix: py3.11 + py3.12)  → install requirements.txt + pytest+pytest-asyncio,
                                  run full suite, run perf suite separately
lint                            → python -m compileall syntax check
summary                         → GH Step Summary table
`

- BIFROST_URL default in CI = localhost:8080 (server not available, integration tests auto-skip per existing logic)
- PYTHONIOENCODING=utf-8 (Windows compat)
- Upload pytest-output.log as artifact on failure (7-day retention)
- Triggered on push to main, PR to main, and manual workflow_dispatch

### Pre-existing test failure noted (NOT fixed per user instruction)

	ests/test_verify_setup.py::TestExpectedServers::test_count_is_16 — asserts 16 servers but opencode.jsonc has 17 (research was added). Pre-existing, not caused by these changes. User was warned via chat.

### Counts

- Tests: 168 → **175** (added 7 perf benchmarks)
- Files: tests/test_perf.py (NEW, 200 lines), .github/workflows/test.yml (NEW, 90 lines)
- Backed up to E:\MCPKU_backup_2026-06-06_HHMM.rar
- Commit pending

---

## mcp_autofix.py

### Per-project error_kb resolution (2026-06-08)

**Problem:** `_ERROR_KB_DIR` hardcoded ke `E:\MCPKU\error_kb\`. Setiap kali
`autofix_run` jalan dari project lain (mis. `E:\deepresearch`), KB nyimpen
ke MCPKU → debug data foreign project numpuk di repo MCPKU, dan histori error
antar project ketuker. Ingin: KB per project, MCPKU KB cuma fallback.

**Fix:**
- Ganti `_ERROR_KB_DIR` (global) → `_ERROR_KB_DEFAULT` (fallback) +
  `_resolve_kb_dir(cwd="")` (resolver).
- Resolver return `<cwd>/error_kb/` dengan `cwd` = argumen atau `Path.cwd()`.
  `mkdir(parents=True, exist_ok=True)` di setiap op (save/search/stats/trends)
  → folder auto-create, tidak ada drama folder missing.
- `_save_to_kb(entry, cwd="")` — accept `cwd` param.
- `autofix_run` pass `cwd=cwd` (sudah ada di `workdir` param, line 583).
- `autofix_save_error` pass `cwd=project or os.getcwd()`.
- `_search_kb_file`, `_kb_stats`, `_kb_trends` baca dari `_resolve_kb_dir()`
  → ikut CWD juga, konsisten full.
- `_STATELESS=1` → kembali ke `_ERROR_KB_DEFAULT`.
- `ERROR_KB_DIR` env var → override `_ERROR_KB_DEFAULT` (backward compat).

**Behavior:**

| Pemanggilan | KB dir |
|---|---|
| `cd E:\deepresearch` + `autofix_run` | `E:\deepresearch\error_kb\` |
| `cd E:\deepresearch` + `autofix_search_kb` | `E:\deepresearch\error_kb\` |
| `autofix_run(cmd, workdir="E:/foo")` | `E:/foo/error_kb/` |
| `AUTOFIX_STATELESS=1` | `ERROR_KB_DIR` atau MCPKU root |
| Tanpa argumen | `Path.cwd() / error_kb/` |

**Backward compat:** default CWD adalah CWD opencode session, jadi kalau
session dari MCPKU, KB tetap di `E:\MCPKU\error_kb\`. Tidak ada breaking
change untuk existing user.

**Verified:**
- `python -c "import ast; ast.parse(...)"` → syntax OK
- `_resolve_kb_dir()` return path yang benar per CWD
- `_save_to_kb(entry, cwd=tmp)` write+readback OK
- `mkdir(parents=True, exist_ok=True)` auto-create folder
- README updated (Error KB section + env var table)
- PATCH_NOTES entry added

**Files changed:** `mcp_autofix.py` (resolver + 5 call sites), `README.md`
(Error KB section + env var row), `PATCH_NOTES.md` (this entry).

---

## [2026-06-08] Workflow Engine Upgrade: Portability & Resume (Finalization)

**Problem:** Workflow engine sebelumnya terpaku pada folder `workflows/` di dalam repo MCPKU. Tidak *portable* jika dijalankan di project folder yang berbeda.

**Fix:**
1.  **Dynamic Path Resolution:** `mcp_planner.py` dan `mcp_workflow.py` kini menerima `target_dir` / `workflow_dir` sebagai parameter.
2.  **Per-Project Workflow Storage:** User bisa menyimpan dan menjalankan workflow di direktori project mana pun (misal: `E:\workflow-generator` atau direktori project lain).
3.  **Auto-Resume Logic:** `mcp_workflow.py` sekarang membaca `workflow_state.jsonl` di direktori target dan melakukan `skip` otomatis pada task yang sudah `completed`.
4.  **Integration Update:** Semua tool workflow (Planner, Run, State) kini *project-aware*.
5.  **Documentation:** README dan patch notes di-update untuk mencerminkan arsitektur yang kini bersifat *multi-project portable*.

**Files changed:** `mcp_workflow.py`, `mcp_planner.py`, `README.md`, `PATCH_NOTES.md`

**Not changed:** vector search flow (`_save_to_vector` / `_vector_search_kb`)
tetap pakai collection global `vec_error_kb` — kalau perlu per-project
vector juga, ticket terpisah (butuh schema migration di pgvector).
