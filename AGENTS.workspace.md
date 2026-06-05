# AGENTS.md — Workspace Rules (E:\)

Rules yang auto-loaded oleh OpenCode untuk semua project di E:\.

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

## Reference: rule persisted di MCP memory
- Entity: `AutofallbackRule` di `E:\MCPKU\memory.jsonl`
- Snapshot markdown: `E:\memory ai\memory-YYYY-MM-DD.md`
- Use `search_nodes("autofallback")` atau `open_nodes(["AutofallbackRule"])` via MCP `memory` tool

## Security hygiene
- Jangan commit `memory.jsonl` (user data) ke public repo
- Jangan expose PAT / API key di remote URL — pakai SSH atau credential helper
- File `AGENTS.md` ini jangan commit kalau ada info sensitif
