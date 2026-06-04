# Contoh Penggunaan MCPKU

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

## 2. Debug error yang nggak kamu mengerti

Prompt:
> "Jalankan `python app.py`, kalau error cari solusinya otomatis"

MCPKU akan:
1. `bash` — jalankan `python app.py`
2. `diagnostics` — parse traceback, klasifikasi error type
3. `autofix` — cari fix strategy
4. `web` + `search_stackoverflow` + `search_github` — cari solusi paralel
5. `autofix` — apply fix, retry
6. `filesystem` — kalau gagal, simpan error ke `error_kb/`
7. Kamu tinggal baca hasilnya

---

## 3. Nyari referensi kode real-time

Prompt:
> "Cari cara fetch API di Node.js pake async/await. Cek Stack Overflow + MDN + npm."

MCPKU akan:
1. `search_stackoverflow("nodejs async await fetch")` — 3 hasil SO
2. `search_mdn("fetch api")` — dokumentasi resmi MDN
3. `search_npm("node-fetch")` — package terbaru
4. Semua dalam 1-2 detik paralel

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

## 9. Belajar teknologi baru

Prompt:
> "Cari tau cara pake async/await di Rust. Kasih contoh code"

MCPKU akan:
1. `search_crates("tokio")` — cari crate async
2. `search_web("rust async await tutorial")` — cari tutorial
3. `search_stackoverflow("rust async await explained")` — cari penjelasan
4. Kembalikan 3 sumber sekaligus

---

## 10. Full pipeline: error → search → fix → KB → commit

Skenario nyata:

```
$ python deploy.py
❌ Error: ModuleNotFoundError: No module named 'boto3'
  ↓
📚 Cek error KB... (tidak ada history)
  ↓
🛠  pip install boto3
  ↓
✅ Fix berhasil, retry...
  ↓
$ python deploy.py ✅ sukses
  ↓
💾 Error disimpan ke error_kb/ untuk referensi
  ↓
✅ git commit -m "deploy: add boto3 dependency"
```

Semua terjadi otomatis tanpa kamu intervensi.

---

## 11. Parallel Research Orchestrator (mcp_research)

`mcp_research` adalah MCP server ke-17 yang menjalankan **9+ source paralel** dengan confidence scoring dalam 1 call. Ganti ritual "search 1-by-1" jadi single call.

**4 tools tersedia:**

| Tool | Sumber | Timeout | Use case |
|---|---|---|---|
| `query(q, err?)` | 9 (mdn, so, npm, pypi, crates, mcp, diagnostics, error_kb, memory) | 6s/task | Default: general lookup |
| `quick(q)` | 2 (mdn + so) | 4s/task | Reference cepat, low-stakes |
| `deep(q, err?)` | 10 (+ web, devdocs) | 8s/task | Error serius, butuh cross-validate |
| `stream(q, err?)` | 5 (as-completed) | 15s total | Stream hasil pertama → kedua → ... |

**Contoh pakai `query()`:**

```
> "Cara fix asyncio.gather hang di Python"

MCPKU panggil:
  mcp_research.query(
    question="asyncio.gather hang event loop",
    error_text="RuntimeError: Event loop is blocked"
  )

Hasil (dalam ~6 detik):
  ✅ 9/9 sources responded
  📊 Confidence: 72/100 (medium)
  📌 Top 3: stackoverflow, mdn, error_kb
  💡 Verdict: "Medium confidence (72/100). 4 sources agree.
            Apply with minor verification."
  🛠  Fix: wrap sync calls in asyncio.to_thread
```

**Contoh pakai `stream()` (real-time):**

```
> mcp_research.stream("playwright cmdk dropdown", "only 5 models per page")

Stream chunks as they arrive:
  [t=0.4s] [stack overflow w=0.90] ── "use page.keyboard.press + ..."
  [t=1.2s] [mdn w=0.95] ── "React controlled input requires ..."
  [t=2.8s] [error_kb w=0.95] ── "no prior error in KB"
  [t=3.1s] [memory w=0.75] ── "no related memory"
  ─── EARLY CONFIDENCE: 60/100 (medium) from 4 sources ───
```

**Confidence scoring:**
- coverage 0-30 (seberapa banyak source return)
- agreement 0-30 (seberapa mirip jawaban)
- weight 0-20 (total source weight)
- bonus 0-20 (error_kb + diagnostics match)
- total 0-100
- verdict: high(75+)/medium(50+)/low(25+)/very_low(<25)

**Source weights** (otomatis):
```
mdn = error_kb = 0.95    # official docs + KB
stackoverflow = 0.90     # community
github = devdocs = diagnostics = 0.85
pypi = npm = crates = 0.80
memory = 0.75
web = 0.50               # generic web lowest
```

---

## 12. Parallel Batching Pattern (kunci performa)

Sejak v17, 4 server (autofix, diagnostics, think, memory) punya instruksi "PARALLEL ORCHESTRATION" di deskripsinya. Intinya: **jangan 1-by-1, kumpulkan semua call independen dalam 1 pesan**.

**❌ LAMA (sequential, ~30s):**
```
1. mcp_diagnostics.classify_error(err)          [5s]
2. mcp_web.search_stackoverflow(q)              [4s]
3. mcp_web.search_mdn(q)                        [3s]
4. mcp_research.error_kb(q)                     [2s]
─────────────────────────────────────────────────
Total: 14s sequential
```

**✅ CEPAT (parallel batch, ~6s):**
```
┌─ mcp_diagnostics.classify_error(err)  [5s] ─┐
├─ mcp_web.search_stackoverflow(q)      [4s] ─┤
├─ mcp_web.search_mdn(q)                [3s] ─┼─ all in 1 message
├─ mcp_research.error_kb(q)             [2s] ─┘
─────────────────────────────────────────────────
Total: max(5,4,3,2) = 5s
```

**Pattern di OpenCode prompt:**
```
"Diagnosa error ini + cari solusi paralel:
 - mcp_diagnostics classify
 - mcp_web search SO + MDN
 - mcp_research query
 Jalankan SEMUA dalam 1 batch, jangan tunggu satu-satu."
```

**Asyncio gotcha yg sudah difix:**
- `asyncio.wait_for(gather(...))` cancel semua kalau 1 lambat → pakai per-task wait_for
- `asyncio.to_thread(sync_fn)` cancel await tapi thread tetap jalan (acceptable)
- `mcp_cache` Redis socket timeout 30s kalau Redis down → fix `socket_connect_timeout=1`

---

## Bonus: Kombinasi referral tools

Prompt yang paling maksimal pakai query multi-source:

> "search_stackoverflow: 'how to use asyncio gather' + search_mdn: 'async await' + search_npm: 'asyncio'"
