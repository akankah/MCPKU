# MCPKU — Patch Notes

Semua perubahan berdasarkan review kode aktual. Setiap fix disertai alasan dan lokasi yang tepat.

---

## mcp_wrapper.py
### NEW: Auto-diagnostics wrapper for MCP servers (Windows)
1. **Wrapper script** — spawn MCP server, capture stderr, inject diagnostics JSON on error detection
2. **Usage**: `python mcp_wrapper.py <server_file.py> [args...]`
3. **Benefit**: Model receives parsed error context without manual tool calls
4. **Keywords**: "error", "traceback", "exception", "timeout", "failed", "timed out"
5. **Output**: `{"_mcpku_diagnostics": {"error_types": [...], "parsed": {...}, "suggestion": "..."}}`

## opencode.jsonc
### Windows MCP startup fix (28 servers)
1. **cmd /c wrapper** — All 28 Python server commands wrapped for Windows .exe resolution
   - Sebelum: `["python", "E:/MCPKU/mcp_bash.py"]`
   - Sesudah: `["cmd", "/c", "python", "E:/MCPKU/mcp_bash.py"]`
2. **Per-server timeout** — Override 30s default (causes timeout under parallel load)
   - All Python servers: `timeout: 60000`
   - context7 (Node.js): `timeout: 120000` (tools/list ~55s external API)
3. **Fix result**: 28/28 servers connect on Windows opencode v1.17.3

## mcp_doc_intel.py
### Lazy imports for optional dependencies
1. **BEFORE**: Import pypdf, python-docx, pandas at module level (startup hang risk)
2. **AFTER**: Lazy load inside tool functions (`_check_pdf()`, `_check_docx()`, `_check_xlsx()`)
3. **Benefit**: FastMCP initializes quickly → MCP handshake completes under parallel load
4. **Heavy deps**: Only load when tool actually called

## mcp_diagnostics.py
### New MCP error patterns + fix suggestions
1. **MCP.Timeout** — `Operation timed out after \d+ms`
   - Suggestion: Add `cmd /c` wrapper + `timeout: 60000+` per server + lazy-load imports
2. **MCP.RequestTimeout** — `MCP error -32001: Request timed out`
   - Suggestion: Increase timeout to `120000+` for affected server
3. **MCP.SpawnFailed** — `Unrecognized key: mcpServers`
   - Suggestion: Change config key from `mcpServers` → `mcp` (opencode v1.17+)
4. **General.LogError** — `^\s*\[\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\]\s+ERROR\b`
   - Suggestion: ERROR log entry. Check full traceback below for root cause.
5. **General.ValidationError** — `validation error for \w+`
   - Suggestion: Pydantic validation error. Check input data matches expected schema.
6. **General.InvalidJSON** — `Invalid JSON:`
   - Suggestion: Invalid JSON input. Ensure valid JSON-RPC format.

## mcp_autofix.py
### New fix handlers for MCP timeout errors
1. **MCP.Timeout** → `_h_mcp_timeout_config` — Suggest cmd/c wrapper + timeout:60000+
2. **MCP.RequestTimeout** → `_h_mcp_request_timeout` — Suggest timeout increase to 120000+
3. **MCP.SpawnFailed** → `_h_mcp_timeout_config` — Suggest fix config schema (mcpServers→mcp)
4. Auto-saves MCP timeout errors to error_kb/ for future reference
5. Falls back to web/GitHub/StackOverflow search if no automatic fix

## verify_setup.py
### Updated sync & check functions
1. **cmd_sync()** — Now reads mcp section from repo's opencode.jsonc (canonical source)
2. **Expected servers** — Updated to 28 servers (added: planner, visualizer, sysmon, ocr, git_doc, api_tester, perf_fixer, refactor, doc_intel, media)
3. **check_paths()** — Updated to accept cmd/c wrapper format (`["cmd", "/c", "python", ...]`)
4. **Auto-backup** — On sync, backs up global config to `.config_backup/opencode.jsonc.global`
5. **Result**: 28/28 servers registered & validated

## mcp_research.py
### Research v3: 9+ source parallel semantic consensus
1. **query(q, err?)** — 9 sources (mdn, so, npm, pypi, crates, mcp, diagnostics, error_kb, memory) — 6s
2. **quick(q)** — 2 sources (mdn + so) — 4s
3. **deep(q, err?)** — 10 sources (+ web, devdocs) — 8s
4. **stream(q, err?)** — 5 sources (as-completed) — 15s total
2. **Confidence scoring**: Coverage (0-30) + Agreement (0-30) + Weight (0-20) + KB bonus (0-20)
3. **Source weights**: mdn=error_kb=0.95, so=0.90, github/devdocs/diagnostics=0.85, pypi/npm/crates=0.80, memory=0.75, web=0.50

## Miscellaneous
- **memory.jsonl** — Personal knowledge graph (auto-created, gitignored)
- **error_kb/** — Per-project error KB (auto-created, gitignored)
- **.config_backup/** — Gitignored backup of global config
- **.provider-free-models.txt** — Personal guide to free providers (gitignored)