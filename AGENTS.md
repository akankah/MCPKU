# MCPKU Project Rules

Project: Python MCP (Model Context Protocol) servers for opencode CLI.
Owner: akankah. All MCPs use stdlib + small deps. Single-file modules.

## Autofallback Rule (HARD, project-wide)

**Default to internet first, always.** When working in this repo:

- `think` tool called → BEFORE thinking, run a websearch / research / webfetch
- **Lag > 10 seconds reasoning without progress → STOP, batch websearch + stackoverflow in one round-trip**
- Error / failure → websearch the exact error text first
- API syntax / header / endpoint / library version unknown → websearch
- Reasoning circular / stuck 2+ retries → websearch the question
- Unknown library or framework → websearch the docs before guessing
- **Mandatory Logging:** Setiap kali alat riset otomatis dipicu, agen WAJIB mencatat ringkasan aktivitas ke `E:\MCPKU\RESEARCH_STATS.md` di akhir sesi.

This rule overrides the model default of "think more." The 10s budget is non-negotiable.

Skip websearch ONLY for:
- Standard algorithms (sort, search, graph, hash) with 100% clear context
- Self-contained bugs with 100% clear context
- Trivial syntax fixes

**Internet sources, in order:**
1. Official docs (docs.z.ai, modelcontextprotocol.io, fastmcp, etc.)
2. GitHub Issues / Discussions of the relevant repo
3. Stack Overflow (with `min_score` filter)
4. Web (DuckDuckGo default)

## Project Structure

- `mcp_*.py` — one MCP server per file. stdlib HTTP/stdio. FastMCP framework.
- `tests/` — pytest suites. Each MCP has its own `test_mcp_*.py`.
- `error_kb/` — runtime error KB (auto-populated by `mcp_autofix.py`).
- `memory.jsonl` — user memory (NEVER commit, has personal data).
- `opencode.jsonc` — project opencode config (mcp servers only).
- `URLS.md` — pre-curated internet reference URLs (use `web_fetch_url` on these).
- `AGENTS.global.md` / `AGENTS.workspace.md` — policy docs.

## Allowed Directories (mcp_filesystem)

Default allows **full `C:\` and `E:\` drives**. Set:
- `MCP_FS_ALLOW_ALL=0` — strict whitelist
- `MCP_EXTRA_ALLOWED_DIR` — comma-sep extras

## MCP Server Conventions

- Single-file, stdlib-first.
- Print logs to **stderr** (stdout is reserved for MCP protocol).
- Async tools via `fastmcp`. Sync tools via stdlib decorators.
- Always include docstring on every tool describing args and return shape.
- Errors raise; don't return `{"ok": false}` (FastMCP handles exceptions).

## Git Conventions

- `feat(<scope>): <summary>` / `fix:` / `test:` / `doc:` / `chore:`
- NEVER commit `memory.jsonl` or `error_kb/*.json` (personal + debug).
- NEVER commit secrets. Use env vars for tokens.

## Build / Test

- No build step. Pure Python.
- `python -m pytest tests/ -v` — run all tests.
- `python verify_setup.py` — environment check.
- `pip install -r requirements.txt` — install deps.
