# Research Performance Statistics

| Tanggal | Alasan Pemicu | Hasil | Dampak Latensi | Catatan |
| :--- | :--- | :--- | :--- | :--- |
| 2026-06-07 | Inisialisasi | - | - | Protokol monitoring mulai diaktifkan. |

| 2026-06-07 | User tanya timeout Context7 MCP saat start opencode | Web search 4 hasil relevan: issue #1244 (hang) & #882 (3 min connect). Fix: naikkan `timeout` di config, atau disable. Tidak ada referensi langsung ke root cause spesifik user — solusi generik diberikan. | ~3s (1 round-trip paralel web_fetch + web_search) | - |
| 2026-06-07 | User tanya permission/lock MCPKU agar model lain tidak edit kode | Web fetch 2 docs: `opencode.ai/docs/permissions` & `opencode.ai/docs/agents`. Konfirmasi: rule match by tool name, MCP tool di-prefix `mcp_<server>_<tool>`, last matching wins. Grep 3 file (`mcp_filesystem.py`, `mcp_git.py`, `mcp_bash.py`, `mcp_autofix.py`) untuk list tool mutating lengkap. | ~5s (1 round-trip fetch docs + grep paralel) | Config ditulis ke `E:\MCPKU\opencode.jsonc` (project-level), 23 rules: built-in edit/write + 8 mcp_filesystem mutating + mcp_bash (deny total) + 2 mcp_autofix + 10 mcp_git mutating. Validasi dengan json5. |

| 2026-06-07 | Copy lock block ke global config | Edit `C:\Users\r\.config\opencode\opencode.jsonc` (sama dengan project-level). Validasi json5: 23 rules, 17 MCP servers. | <1s (cuma edit file + validate) | Lock sekarang aktif di semua CWD, bukan hanya E:\MCPKU. |

| 2026-06-07 | User minta update README + push pembaruan | Edit `README.md` (tambah section "Lock — protect MCPKU dari model edits" antara Client config dan Architecture, 46 baris). `git add` 4 file (opencode.jsonc, README.md, mcp_web.py, RESEARCH_STATS.md) → 1 commit `807ccf8 chore(lock): add 23-rule permission block ...` → `git push origin main` sukses (bab35af..807ccf8). Catatan keamanan: remote URL mengandung PAT (ghp_...), sebaiknya dipindah ke SSH/credential helper. | ~3s (1 edit + 1 commit + 1 push) | mcp_web.py change sebenarnya pre-existing (search_mdn tool) — ikut ke-commit karena user minta push semua pembaruan. |

| 2026-06-07 | Migrasi remote HTTPS+PAT → SSH | `ssh-keygen -t ed25519 -C "akankah@MCPKU" -f ~/.ssh/id_ed25519` (no passphrase). User add public key manual ke https://github.com/settings/keys (title: `MCPKU-Win11`, fingerprint `SHA256:peodYNq2hW7jHgx7ALMorma0qeS35N5PC/3kJTiX+2c`). `git remote set-url origin git@github.com:akankah/MCPKU.git`. Verify: `ssh -T git@github.com` → `Hi akankah! You've successfully authenticated`. `git fetch origin` exit 0. User declined revoke token lama (PC pribadi, single user). Final commit + push `chore: log SSH migration session`. | ~30s (1 ssh-keygen + 1 manual browser step user + 2 git commands) | Note: token `ghp_M7ju...` di URL lama masih aktif per pilihan user — risiko rendah karena single-user PC. |

| 2026-06-07 | User minta lock dari deny → ask (model harus minta ijin dulu) | Edit 2 config (project + global) replace `"deny"` path-rules → `"ask"`. `mcp_bash_run_command` dari deny-total → path-based pattern (allow non-MCPKU, ask kalau command string menyentuh MCPKU). `mcp_autofix_run/save_error` tetap deny. README "Lock" section di-rewrite: judul "Lock with approval", table ganti "Action: ask", tambah "How the prompt looks" + "Tighter lock (deny instead of ask)". Commit `ff784e1 chore(lock): switch from deny to ask for MCPKU mutations` → push OK (6740748..ff784e1). | ~5s (2 config edit + 1 README edit + 1 commit + 1 push) | Validasi json5: 21 ask, 2 deny di kedua config. |

| 2026-06-07 | Fix pre-existing red test `test_verify_setup.py:84` | Root cause: EXPECTED_SERVERS = 17 (research added in commit `bab35af`), test masih assert == 16. Fix: docstring + method name + assertion ke 17. Run ulang: 10/10 PASS di file ini. Full suite: 164 passed, 11 skipped in 23.07s (sebelumnya 152, sekarang 164 — sesuai dengan 11 skipped bifrost integration). Commit `fix(test): ...` + push OK. | ~30s (grep + read + edit + pytest full + commit + push) | Test skipped (11) = bifrost integration yg butuh live postgres/redis/playwright — expected, bukan regresi. |

| 2026-06-07 | Update README test stats (stale from pre-research era) | Edit 2 spot di README: line 485 (Quick start) 175 tests ~6s → ~23s, line 683 (Tests section) 152 tests/14 modules/~4s → 164 passed+11 skipped/17 modules/~23s. Skip commit 4 untracked `error_kb/*.json` (per AGENTS.md: NEVER commit error_kb/). Commit `doc: update README test counts` + push OK. | ~10s (1 grep + 2 edit + 1 commit + 1 push) | Note: 4 error_kb file baru muncul di CWD (timestamp 12:38 & 12:43 WIB) — indikasi ada MCP run yang error hari ini, di-save otomatis. Tidak di-commit sesuai aturan. |

| 2026-06-07 | User minta naikkan timeout context7 (workaround untuk hang di awal sesi) | Edit 2 config (project + global): tambah `"timeout": 30000` di MCP context7 (default 5000ms). Commit `chore(context7): raise MCP timeout from 5s to 30s` + push OK. | ~3s (2 edit + 1 commit + 1 push) | Note: butuh restart opencode agar perubahan生效. Tidak apply ke README karena sifatnya konfigurasi runtime, bukan dokumentasi. |

| 2026-06-07 | Aktifkan MCPKU di Claude Code (user bilang "claude desktop" tapi Desktop ga ke-install) | Cek: `%APPDATA%\Claude`, `%LOCALAPPDATA%\Claude` — tidak ada. Yang ada: Claude Code CLI v2.1.165 di PATH + Claude Cowork (VM-based, beda produk, di `C:\ProgramData\Claude\Logs\coworkd`, log terakhir 6/6/2026 status `API reachability: UNREACHABLE`). User konfirmasi pakai Code CLI. Edit `C:\Users\r\.claude\settings.json`: preserve env block (ANTHROPIC_BASE_URL/MODEL/API_KEY/TOOL_SEARCH) + tambah mcpServers 17 server (mirroring opencode.jsonc). Env per-server: SQLITE_DB_PATH, LOCAL_TIMEZONE, MCP_EXTRA_ALLOWED_DIR, MCP_FS_ALLOW_ALL, MEMORY_FILE_PATH, REDIS_URL. context7 timeout=30000ms. API key global (FIRECRAWL/STACKEX/GITHUB/DATABASE/OPENAI) diharapkan inherit dari system env. File di $HOME, tidak masuk repo. | ~30s (1 search sistem + 1 read + 1 write + 1 validate) | Lock permission dari opencode.jsonc TIDAK apply di Claude Code (Code tidak punya permission system). MCPKU files akan bisa di-edit bebas kalau pakai Code — beda dengan opencode. |

| 2026-06-07 | Aktifkan MCPKU di Claude Desktop | Cari config: `%APPDATA%\Claude\claude_desktop_config.json` tidak ada (salah lokasi). Yang benar: `C:\Users\r\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json` (AppX/WindowsApps pattern, Roaming\LocalCache). Config sudah ada dengan 17 server + `preferences.coworkWebSearchEnabled: true`. Sync 2 hal yang ketinggalan dari opencode.jsonc: (1) filesystem tambah `MCP_FS_ALLOW_ALL: "1"`, (2) context7 tambah `timeout: 30000`. Catatan: API keys (FIRECRAWL/STACKEX/GITHUB/DATABASE/OPENAI) masih empty string `""` di Desktop config — bisa di-fill manual atau hapus agar inherit dari system env. Tidak restart Desktop (perlu konfirmasi user — 4 claude.exe proses jalan). File di $HOME/AppData, tidak masuk repo. | ~10s (cari + read + 2 edit + 1 validate) | Koreksi: Claude Desktop SUDAH terinstall di WindowsApps (sebelumnya saya bilang tidak ada — salah). |

| 2026-06-07 | Aktifkan MCPKU di Kilo Code CLI v7.3.16 | Kilo npm `@kilocode/cli` ada di `C:\Users\r\AppData\Roaming\npm\kilo`. Config path (kilo.jsonc, sama format opencode): `C:\Users\r\.config\kilo\kilo.jsonc`. Default punya 3 MCP npm (filesystem/postgres/github, semua disabled). Tambah 17 MCPKU server. 3 duplicate-name (filesystem, postgres, github) di-prefix `mcpku_` agar tidak collision dengan npm default. Env block per-server: SQLITE, TIME, FILESYSTEM, MEMORY, REDIS, POSTGRES, VECTOR (mirroring opencode.jsonc). context7 timeout=30000ms. JSON valid via json5. Tidak apply lock permission (kilo existing permission.bash sudah 288+ allow pattern — clash). File di $HOME/.config, tidak masuk repo. | ~30s (2 cari + 1 read + 1 edit + 1 validate) | Note: kilo pakai config format yang sama persis dengan opencode (`$schema: opencode.ai/config.json`) — duplikasi config. Pertimbangkan sync script antara kilo.jsonc ↔ opencode.jsonc. |

| 2026-06-08 | Fix `E:\deepresearch` pipeline: 19→32 confidence, 0/6→4/6 chapters pass | Debug: env loading order (Serper/Firecrawl mati karena import-time vs runtime), `_extract_keywords` regex `{2,}`→`{1,}` (hilangkan "AI" dari query), SO query pakai `question` bukan `keywords` (0 results untuk bisnis Indonesia), `n_active` hitungan (termasuk memory/error strings → coverage tertekan), coverage boost tidak aktif karena `n_active>4`. Fix: load_dotenv sebelum import, regex `{1,}`, SO pakai `question[:80]`, `n_active` exclude `startswith("(")`, boost unconditional untuk single-source, stagger 3s per chapter untuk hindari Serper rate limit, DDG pakai `duckduckgo_search` library. Sources: DDG dead (402), Firecrawl dead (credits expired), Stack Overflow 0 for business topics. Hanya Serper (Google) yang berfungsi. | ~30 search/read/edit + 8 pipeline runs | Serper satu-satunya sumber yang berfungsi untuk topik bisnis Indonesia. Confidence maksimum ~32/100 dengan single source. Perlu sumber kedua (Bing/Google CSE) untuk meningkatkan >50. |

## 2026-06-08 — Integrasi dzhng/deep-research (Iterative LLM Pipeline)

**Aktivitas:**
- Membaca source code dzhng/deep-research (TypeScript, <500 LoC)
- Membuat `src/llm_client.py` — multi-provider LLM client (OpenRouter → Groq fallback)
- Membuat `src/deep_research_llm.py` — Python port of dzhng iterative pattern (4 learnings, 10 URLs per run)
- Memodifikasi `main.py` — add `--mode iterative|chapter` flag
- Memodifikasi `webui.py` — add mode toggle (radio button UI)

**Hasil test (breadth=2, depth=1):**
- 2 search queries generated by LLM
- 5 URLs each via Serper
- 4 learnings extracted by LLM
- Report: ~4900 chars, Indonesian, structured
- Time: ~19s untuk depth=1

**Perubahan signifikan:**
- `llm_client.py` rewritten: multi-provider chain (OpenRouter 402 → Groq free tier works)
- `main.py` refactored: fungsi `_run_chapter_mode()` dan `_run_iterative_mode()` terpisah
- `webui.py` updated: mode selector, dynamic params, adaptive render

**Next:**
- Test breadth=3, depth=2 untuk report lebih dalam
- Jika Groq rate-limited, tambah Gemini fallback (key ada di .env)
- Deploy web UI dan test dari browser
