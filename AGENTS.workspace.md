# AGENTS.md — User-level OpenCode Rules

Rules yang auto-loaded oleh OpenCode untuk SEMUA project (di mana pun lokasinya).

## Autofallback Rule (aggressive — force internet)

**Prinsip:** Internet dulu, mikir kemudian. Jangan buang waktu trial-error sendiri kalau web bisa jawab dalam 1 query.

### WAJIB internet (websearch / research / webfetch) — JANGAN skip:
- **`think` tool dipanggil** → sebelum mikir, cari referensi internet dulu
- **Lag > 10 detik** → stop, langsung search, jangan nunggu
- **Error / failure** → langsung search error, jangan coba fix sendiri
- **Analisa / reasoning** → cari referensi internet sebagai basis analisa
- **Sintaks cepat berubah** (UUID, header, endpoint, library) → search dulu
- **Debug service eksternal** → search behavior + intercept request
- **Reasoning circular / stuck** → stop, force search
- **API key/library update** (reCAPTCHA, Cloudflare, NPM) → search dulu
- **Gagal 1x aja** → langsung search, jangan coba ulang tanpa referensi

### Code Error Fallback — WAJIB
- **Kode error / gagal run** → langsung search referensi internet, jangan coba ulang tanpa referensi
- **Compile/runtime error di kode yg ditulis AI** → search error + fix sebelum ngulang
- **Chat response mengandung "gagal" / "failed" / "tidak bisa" / "unable"** → force search internet untuk referensi, jangan jawab asal
- **Semua model** kena rule ini — bukan cuma model tertentu, semua dipaksa

### Skip search — ONLY these:
- Algoritma standar (sort, search, graph, hash)
- Bug di kode sendiri yang konteksnya 100% jelas
- Confidence > 95% di jawaban model (hampir tidak pernah)

### Anti-pattern — JANGAN:
- Trial-and-error pakai model knowledge untuk hal yang bisa di-search dalam 1 query
- Nunggu 2-3x failure sebelum search
- Asumsi "knowledge cutoff terbaru" tanpa verify
- Mikir sendiri >10 detik tanpa web search

---

## Referensi Internet — sumber yang dipakai (prioritas)

**Prinsip:** Pakai sumber yang **paling cepat + paling otoritatif** untuk domain yang ditanya. Jangan default ke Stack Overflow untuk hal baru.

### Prioritas 1 — AI (cocok untuk apa saja, tapi HARUS verify)
- ChatGPT, Claude, Gemini, Cursor, Windsurf, GitHub Copilot
- **Selalu verify** jawaban AI ke dokumentasi resmi / GitHub Issues / diskusi maintainer

### Prioritas 2 — Dokumentasi resmi (WAJIB untuk API, framework, library)
- **MDN Web Docs** — HTML, CSS, JS, Web API
- **Dokumentasi resmi framework** — React, Next.js, Vue, Svelte, dll (cek docs.framework.dev)
- **NPM/PyPI/Crates** — package, version, changelog
- **Context7 MCP** — untuk doc library yang up-to-date (ada di MCPKU)

### Prioritas 3 — Komunitas maintainer & diskusi (untuk masalah baru / niche)
- **GitHub Discussions & Issues** — pertanyaan dijawab langsung maintainer, WAJIB cek dulu sebelum nanya
- **Discord komunitas** — React, Next.js, Vue, Cursor, Anthropic, Vercel, Supabase, framework spesifik
  - Kelebihan: jawaban menit, diskusi 2-arah, maintainer aktif
  - Kekurangan: sulit dicari ulang, kualitas tidak konsisten, mudah tenggelam

### Prioritas 4 — Stack Overflow (klasik, error umum)
- Paling efisien untuk: error klasik, algoritma, syntax, library lama
- **Turun drastis** popularitasnya untuk masalah baru (AI, MCP, framework 2025+)

### Prioritas 5 — Forum latihan (opsional, untuk belajar algoritma)
- LeetCode, HackerRank — ada forum diskusi solusi

### Panduan pilih sumber (kapan pakai apa)
| Masalah | Sumber pertama |
|---|---|
| Error runtime klasik (TypeError, import, syntax) | [MDN](https://developer.mozilla.org/) + [Stack Overflow](https://stackoverflow.com/) + AI |
| API/endpoint library baru (UUID, header, version) | [Dokumentasi resmi framework](https://devdocs.io/) + [GitHub Issues](https://github.com/search?q=is%3Aissue&type=issues) |
| Framework baru (Next.js 15, React 19, MCP) | [Next.js Discord](https://discord.gg/nextjs) / [Reactiflux](https://www.reactiflux.com/) + [GitHub Discussions](https://github.com/search?q=is%3Adiscussion&type=discussions) + AI |
| Algoritma/data structure | [LeetCode](https://leetcode.com/discuss/) + AI |
| Deployment, infra (Vercel, Supabase) | [Vercel Discord](https://discord.gg/vercel) / [Supabase Discord](https://discord.gg/supabase) + AI |
| Library NPM/Python update | [Context7](https://context7.com/) + [NPM](https://www.npmjs.com/) / [PyPI](https://pypi.org/) + changelog |
| Bug di kode sendiri | AI dulu, lalu [GitHub Issues](https://github.com/search?q=is%3Aissue&type=issues) kalau aneh |

> **Daftar lengkap URL** lihat [`URLS.md`](../MCPKU/URLS.md) di MCPKU — skip searching, langsung `web_fetch_url`.

### Anti-pattern referensi
- Nanya AI tanpa verify → **dilarang**, AI sering ngaco untuk API version baru
- Asumsi SO jawabannya up-to-date → cek tanggal post
- Skip dokumentasi resmi → **dilarang**, AI tidak lebih otoritatif dari docs
- Trust random Medium/Dev.to article tanpa cek tanggal dan author

---

## Session-start checklist
1. Jika model merasa ragu atau ada error yang berulang → `search_nodes` di MCP memory
2. Pertanyaan tentang user preference → `open_nodes` di MCP memory
3. Untuk konteks user → cek `E:\memory ai\memory-YYYY-MM-DD.md` (snapshot harian)

## Security hygiene
- Jangan commit `memory.jsonl` (user data) ke public repo
- Jangan expose PAT / API key di remote URL — pakai SSH atau credential helper
- File `AGENTS.md` ini jangan commit kalau ada info sensitif

## Reference
- MCPKU code: `E:\MCPKU\`
- MCP memory: `E:\MCPKU\memory.jsonl` (entities, observations)
- User memory snapshots: `E:\memory ai\memory-YYYY-MM-DD.md`
- Workspace-level rules: `E:\AGENTS.md` (apply ke E:\* saja)
