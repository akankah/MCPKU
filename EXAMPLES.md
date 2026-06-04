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

## Bonus: Kombinasi referral tools

Prompt yang paling maksimal pakai query multi-source:

> "search_stackoverflow: 'how to use asyncio gather' + search_mdn: 'async await' + search_npm: 'asyncio'"
