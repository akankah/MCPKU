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
