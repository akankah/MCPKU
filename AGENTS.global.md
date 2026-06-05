# AGENTS.md — User-level OpenCode Rules

Rules yang auto-loaded oleh OpenCode untuk SEMUA project (di mana pun lokasinya).

## Autofallback Rule (aggressive — force internet)

**Prinsip:** Internet dulu, mikir kemudian. Jangan buang waktu trial-error sendiri kalau web bisa jawab dalam 1 query.

### WAJIB internet (websearch / research / webfetch) — JANGAN skip:
- **`think` tool dipanggil** → sebelum mikir, cari referensi internet dulu
- **Lag > 20 detik** → stop, langsung search, jangan nunggu
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
- Mikir sendiri >20 detik tanpa web search

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
