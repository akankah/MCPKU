# Contoh Penggunaan MCPKU (28 Servers)

## 1. Full-stack app dalam 1 prompt

Prompt:
> "Buat REST API Express dengan SQLite, routes CRUD untuk tasks, terus deploy sebagai script single-file. Test semua endpoint."

MCPKU akan:
1. `filesystem` — buat file `server.js`
2. `bash` — `npm init`, `npm install express better-sqlite3`
3. `bash` — jalankan server, test dengan curl
4. `diagnostics` + `autofix` — auto-fix kalau ada error
5. `git` — commit hasilnya

---

## 2. Debug error yang nggak kamu mengerti (Auto-Recovery)

Prompt:
> "Jalankan `python app.py`, kalau error cari solusinya otomatis"

MCPKU akan:
1. `bash` — jalankan `python app.py`
2. `diagnostics` — parse traceback, klasifikasi error type
3. `autofix` — cari fix strategy
4. `research` — `query(q, err)` — cari solusi paralel (9 sources)
5. `autofix` — apply fix, retry
6. `filesystem` — kalau gagal, simpan error ke `<cwd>/error_kb/`
7. Kamu tinggal baca hasilnya

---

## 3. Nyari referensi kode real-time (Parallel Research)

Prompt:
> "Cari cara fetch API di Node.js pake async/await. Cek Stack Overflow + MDN + npm."

MCPKU akan:
1. `research.query("nodejs async await fetch")` — jalankan pencarian paralel ke:
   - Stack Overflow
   - MDN Web Docs
   - npm registry
   - PyPI / crates.io / DevDocs
2. Mengembalikan hasil terurut berdasarkan semantic similarity dalam ~5 detik

---

## 4. Auto-fix error berulang

Prompt:
> "Jalankan server, kalau error 'port in use' kill processnya otomatis"

MCPKU akan:
1. `bash` — `node server.js`
2. ❌ Error `EADDRINUSE`
3. `autofix` — detect `EADDRINUSE`, jalankan `taskkill /PID` (Windows) atau `lsof -ti:PORT | kill` (Unix)
4. Retry otomatis
5. ✅ Server jalan

---

## 5. Multi-session error tracking

Prompt:
> "Cek tren error seminggu terakhir"

MCPKU akan:
1. `autofix_kb_trends(days=7)` — tampilkan:
   - Total error
   - Error type terbanyak
   - Project paling bermasalah
   - Fix rate
   - Per-hari chart

---

## 6. GitHub automation

Prompt:
> "Cari issue open tentang 'memory leak' di repo expressjs/express, terus bikin PR description"

MCPKU akan:
1. `search_issues("memory leak", repo="expressjs/express")` — cari issues
2. `search_stackoverflow("express memory leak")` — cari solusi
3. Kamu tinggal review + bikin PR

---

## 7. One-shot setup project

Prompt:
> "Buat project Python Flask + SQLite + React frontend, initialize git, terus push ke GitHub"

MCPKU akan:
1. `bash` — `mkdir project`, `pip install flask`
2. `filesystem` — buat `app.py`, `frontend/`
3. `bash` — `npx create-react-app frontend`
4. `git` — `init`, `add`, `commit`
5. `github` — create repo, push

---

## 8. Autonomous coding session

Prompt:
> "Baca file `buggy.py`, cari bug, fix, test, commit"

MCPKU akan:
1. `filesystem` — baca `buggy.py`
2. `bash` — jalankan, ❌ error
3. `diagnostics` — parse error
4. `autofix` — fix + retry
5. `bash` — test lagi
6. `git` — commit "autofix: ..."

---

## 9. Local Document Intelligence (mcp_doc_intel)

Prompt:
> "Baca isi file PDF 'invoice.pdf' dan ambil total tagihannya"

MCPKU akan:
1. `doc_intel.read_pdf("invoice.pdf")` — ekstrak teks (lazy-loads `pypdf` otomatis)
2. Menganalisis teks dan mengambil total tagihan tanpa external API/cloud call

---

## 10. System Monitoring & Process Management (mcp_sysmon)

Prompt:
> "Cari proses python yang makan RAM paling banyak terus kill"

MCPKU akan:
1. `sysmon.list_top_processes(sort_by="memory", limit=5)` — tampilkan proses teratas
2. `sysmon.kill_process(pid=PID)` — kill proses python yang bermasalah

---

## 11. Smart Refactoring & formatting (mcp_refactor)

Prompt:
> "Bersihkan dan format file auth.py dari unused imports"

MCPKU akan:
1. `refactor.clean_python_code("auth.py")` — jalankan `autoflake` + `black` otomatis
2. `refactor.check_code_smells("auth.py")` — cek cyclomatic complexity / deep nesting

---

## 12. Parallel Research Orchestrator (mcp_research)

`mcp_research` adalah MCP server ke-28 yang menjalankan **9+ source paralel** dengan confidence scoring dalam 1 call. Ganti ritual "search 1-by-1" jadi single call.

**4 tools tersedia:**

| Tool | Sumber | Timeout | Use case |
|---|---|---|---|
| `query(q, err?)` | 9 (mdn, so, npm, pypi, crates, mcp, diagnostics, error_kb, memory) | 6s/task | Default: general lookup |
| `quick(q)` | 2 (mdn + so) | 4s/task | Reference cepat, low-stakes |
| `deep(q, err?)` | 10 (+ web, devdocs) | 8s/task | Error serius, butuh cross-validate |
| `stream(q, err?)` | 5 (as-completed) | 15s total | Stream hasil pertama → kedua → ... |

---

## 13. Auto-Diagnostics Wrapper (mcp_wrapper)

`mcp_wrapper.py` meng-intercept stderr/stdout dari semua server Python. Jika mendeteksi error pattern, wrapper auto-inject diagnostics JSON ke stderr.

**Alur:**
```
Subprocess error → wrapper detect "Traceback/ERROR" → mcp_diagnostics classify → inject _mcpku_diagnostics JSON
```
Model menerima parsed error context tanpa harus manual memanggil tools diagnostics.

---

## 14. Parallel Batching Pattern (kunci performa)

Sejak v1.17, 4 server (autofix, diagnostics, think, memory) punya instruksi "PARALLEL ORCHESTRATION" di deskripsinya. Intinya: **jangan 1-by-1, kumpulkan semua call independen dalam 1 pesan**.

**❌ LAMA (sequential, ~15s):**
```
1. mcp_diagnostics.classify_error(err)          [5s]
2. mcp_web.search_stackoverflow(q)              [4s]
3. mcp_web.search_mdn(q)                        [3s]
4. mcp_research.error_kb(q)                     [2s]
─────────────────────────────────────────────────
Total: 14s sequential
```

**✅ CEPAT (parallel batch, ~5s):**
```
┌─ mcp_diagnostics.classify_error(err)  [5s] ─┐
├─ mcp_web.search_stackoverflow(q)      [4s] ─┤
├─ mcp_web.search_mdn(q)                [3s] ─┼─ all in 1 message
├─ mcp_research.error_kb(q)             [2s] ─┘
─────────────────────────────────────────────────
Total: max(5,4,3,2) = 5s
```