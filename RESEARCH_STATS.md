# Research Performance Statistics

| Tanggal | Alasan Pemicu | Hasil | Dampak Latensi | Catatan |
| :--- | :--- | :--- | :--- | :--- |
| 2026-06-12 | B.AI model cleanup + API key setup | Review progress MCPKU (28 MCP servers connect). Test 21 B.AI models — hanya 4 work: gemini-3.5-flash, glm-5.1, glm-5, kimi-k2.5. Update config: hapus 17 non-working, tambah apiKey="${BAI_API_KEY}", set user env var. Sync ke global config. Bersihkan session lama dari RESEARCH_STATS.md. | ~30s (2 edit + 1 set env + 1 sync) | API key disimpan sebagai user env var BAI_API_KEY, bukan hardcode di JSON. |
