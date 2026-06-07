# Research Performance Statistics

| Tanggal | Alasan Pemicu | Hasil | Dampak Latensi | Catatan |
| :--- | :--- | :--- | :--- | :--- |
| 2026-06-07 | Inisialisasi | - | - | Protokol monitoring mulai diaktifkan. |

| 2026-06-07 | User tanya timeout Context7 MCP saat start opencode | Web search 4 hasil relevan: issue #1244 (hang) & #882 (3 min connect). Fix: naikkan `timeout` di config, atau disable. Tidak ada referensi langsung ke root cause spesifik user — solusi generik diberikan. | ~3s (1 round-trip paralel web_fetch + web_search) | - |
| 2026-06-07 | User tanya permission/lock MCPKU agar model lain tidak edit kode | Web fetch 2 docs: `opencode.ai/docs/permissions` & `opencode.ai/docs/agents`. Konfirmasi: rule match by tool name, MCP tool di-prefix `mcp_<server>_<tool>`, last matching wins. Grep 3 file (`mcp_filesystem.py`, `mcp_git.py`, `mcp_bash.py`, `mcp_autofix.py`) untuk list tool mutating lengkap. | ~5s (1 round-trip fetch docs + grep paralel) | Config ditulis ke `E:\MCPKU\opencode.jsonc` (project-level), 23 rules: built-in edit/write + 8 mcp_filesystem mutating + mcp_bash (deny total) + 2 mcp_autofix + 10 mcp_git mutating. Validasi dengan json5. |

| 2026-06-07 | Copy lock block ke global config | Edit `C:\Users\r\.config\opencode\opencode.jsonc` (sama dengan project-level). Validasi json5: 23 rules, 17 MCP servers. | <1s (cuma edit file + validate) | Lock sekarang aktif di semua CWD, bukan hanya E:\MCPKU. |

| 2026-06-07 | User minta update README + push pembaruan | Edit `README.md` (tambah section "Lock — protect MCPKU dari model edits" antara Client config dan Architecture, 46 baris). `git add` 4 file (opencode.jsonc, README.md, mcp_web.py, RESEARCH_STATS.md) → 1 commit `807ccf8 chore(lock): add 23-rule permission block ...` → `git push origin main` sukses (bab35af..807ccf8). Catatan keamanan: remote URL mengandung PAT (ghp_...), sebaiknya dipindah ke SSH/credential helper. | ~3s (1 edit + 1 commit + 1 push) | mcp_web.py change sebenarnya pre-existing (search_mdn tool) — ikut ke-commit karena user minta push semua pembaruan. |
