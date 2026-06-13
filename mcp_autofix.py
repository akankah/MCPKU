"""
mcp_autofix.py — MCPKU Auto-Fix Server
========================================
Closed-loop debugging: run → detect error → parse → apply fix → retry → commit.

Pipeline:
  run command → error detected → parse traceback → classify →
  look up fix strategy → apply fix → retry original command →
  (optional) git commit → report result

Depends on: mcp_diagnostics.py (for parse/classify functions)
"""

import asyncio
import hashlib
import json
import os
import re
import shlex
import struct
import time
from pathlib import Path
from datetime import datetime
from typing import Any
from mcp.server.fastmcp import FastMCP

from mcp_diagnostics import (
    _auto_detect_language,
    _parse_python_traceback,
    _parse_node_traceback,
    _parse_rust_traceback,
    _classify,
)
from mcp_web import search_web, search_stackoverflow
from mcp_github import search_issues
from error_data import FIX_SUGGESTIONS, FIX_STRATEGIES_DESC

mcp = FastMCP(
    "autofix",
    instructions=(
        "Auto-fix server. Run a command, detect errors, apply fixes automatically, "
        "retry, and optionally commit. Use autofix_run whenever a command fails — "
        "this server will parse the error, classify it, apply the correct fix "
        "(pip install, npm install, etc.), and retry. You MUST use this instead of "
        "manually debugging. Only manual debugging if autofix_run fails after all "
        "retries.\n\n"
        "AUTOFALLBACK (mandatory): if the same error recurs 2+ times or reasoning "
        "exceeds 10s without progress → STOP retrying and batch websearch + "
        "stack overflow in one round-trip. Skip search only for trivial fixes "
        "(import, syntax, well-known errors). See AGENTS.md for full rule.\n\n"
        "PARALLEL ORCHESTRATION (mandatory for non-trivial errors):\n"
        "When autofix_run returns an UNKNOWN error or low-confidence fix, "
        "you MUST call the following tools IN PARALLEL within the same tool batch "
        "(one round-trip, not sequential):\n"
        "  - diagnostics.classify_error(error_text)  → confirm error type\n"
        "  - diagnostics.explain_error(error_text)   → get fix explanation\n"
        "  - memory.search_nodes('<error_keyword>')  → check past similar errors\n"
        "  - think.new_session(reasoning='verify autofix result')  → record verification step\n"
        "  - mcp_research(query=...)                 → dedicated parallel orchestrator (calls 6 web sources + diagnostics + memory in one shot)\n"
        "After parallel results return, cross-check: if 3+ sources agree on the fix, "
        "apply it. If sources conflict, return conflict to user.\n\n"
        "Use mcp_research.query() for ONE-SHOT cross-validation when you want autofix + "
        "diagnostics + memory + 6 web sources called in parallel and ranked automatically."
    ),
)

MAX_RETRIES_DEFAULT = 3

_STATELESS = os.environ.get("AUTOFIX_STATELESS", "0") == "1"
_ERROR_KB_DEFAULT = Path(os.environ.get("ERROR_KB_DIR", Path(__file__).parent / "error_kb"))


def _resolve_kb_dir(cwd: str = "") -> Path:
    if _STATELESS:
        return _ERROR_KB_DEFAULT
    base = Path(cwd).resolve() if cwd else Path.cwd()
    return base / "error_kb"

# ── Fix handlers ─────────────────────────────────────────────────────────────
# Each handler takes (error_types, error_text, cwd) and returns
# a list of (command_string, description) tuples.

_Q_STR = re.compile(r"'([^']+)'|\"([^\"]+)\"")


def _first_quoted(text: str) -> str | None:
    m = _Q_STR.search(text)
    return m.group(1) or m.group(2) if m else None


def _h_pip_install(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    mod = _first_quoted(error_text)
    return [(f"pip install {mod}", f"Install Python package '{mod}'")] if mod else []


def _h_npm_install(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    mod = _first_quoted(error_text)
    return [(f"npm install {mod}", f"Install npm package '{mod}'")] if mod else []


def _h_mkdir_parent(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    path = _first_quoted(error_text)
    if path:
        parent = str(Path(path).parent)
        if parent != ".":
            return [(f"mkdir -p \"{parent}\"", f"Create directory '{parent}'")]
    return []


def _h_kill_port(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    port_m = re.search(r':(\d{4,5})', error_text)
    if port_m:
        port = port_m.group(1)
        cmds = []
        if os.name == "nt":
            cmds.append((
                f'netstat -ano | findstr :{port} > %temp%\\_port_{port}.txt '
                f'&& for /f "tokens=5" %p in (%temp%\\_port_{port}.txt) do '
                f'taskkill /PID %p /F 2>nul & del %temp%\\_port_{port}.txt 2>nul',
                f"Kill process on port {port}"
            ))
        else:
            cmds.append((
                f"lsof -ti:{port} | xargs kill -9 2>/dev/null; true",
                f"Kill process on port {port}"
            ))
        return cmds
    return []


def _h_go_mod_tidy(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    return [("go mod tidy", "Run go mod tidy")]


def _h_mcp_timeout_config(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    """Fix for MCP.Timeout: update opencode.jsonc with cmd /c wrapper and timeout."""
    cmds = []
    # Check if opencode.jsonc exists
    config_path = Path(cwd) / "opencode.jsonc"
    if config_path.exists():
        cmds.append((
            f'python -c "import json, sys; data = open(\\\"{config_path}\\\").read(); '
            f'print(\"Config exists, apply manual fix: add cmd /c wrapper and timeout: 60000 to all mcp servers\")"',
            "Check opencode.jsonc exists"
        ))
    return cmds


def _h_mcp_request_timeout(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    """Fix for MCP.RequestTimeout: increase server timeout in config."""
    cmds = []
    config_path = Path(cwd) / "opencode.jsonc"
    if config_path.exists():
        cmds.append((
            f'python -c "print(\\\"Fix: Increase timeout to 120000 for the affected server in opencode.jsonc\\\")"',
            "Increase MCP server timeout"
        ))
    return cmds


def _h_black_format(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    frame_m = re.search(r'File "([^"]+)", line \d+', error_text)
    if frame_m:
        file_path = frame_m.group(1)
        return [(f"black \"{file_path}\"", f"Format '{file_path}' with black")]
    return [("black .", "Format all Python files with black")]


def _h_ping_db(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    return [("python -c \"import socket; socket.gethostbyname('localhost')\"", "Check DB host resolution")]


FIX_HANDLERS: dict[str, callable] = {
    "Python.ImportError": _h_pip_install,
    "Python.ModuleNotFoundError": _h_pip_install,
    "JS.ModuleNotFound": _h_npm_install,
    "Python.FileNotFound": _h_mkdir_parent,
    "JS.ENOENT": _h_mkdir_parent,
    "JS.EADDRINUSE": _h_kill_port,
    "Go.BuildError": _h_go_mod_tidy,
    "Python.IndentationError": _h_black_format,
    "MCP.Timeout": _h_mcp_timeout_config,
    "MCP.RequestTimeout": _h_mcp_request_timeout,
    "MCP.SpawnFailed": _h_mcp_timeout_config,
}

# FIX_STRATEGIES_DESC and FIX_SUGGESTIONS imported from error_data


def _build_fix_commands(error_types: list[str], error_text: str, cwd: str = "") -> list[tuple[str, str]]:
    cmds: list[tuple[str, str]] = []
    for etype in error_types:
        handler = FIX_HANDLERS.get(etype)
        if handler:
            result = handler(error_types, error_text, cwd)
            for cmd, desc in result:
                if cmd not in [c for c, _ in cmds]:
                    cmds.append((cmd, desc))
    return cmds


def _can_auto_fix(error_types: list[str]) -> bool:
    return any(et in FIX_HANDLERS for et in error_types)


_autofix_history: list[dict] = []


def _record(entry: dict) -> None:
    if _STATELESS:
        return
    _autofix_history.append(entry)
    if len(_autofix_history) > 50:
        _autofix_history.pop(0)


async def _run_shell(command: str, cwd: str, timeout: int) -> dict:
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"exit_code": -1, "stdout": "", "stderr": "(timeout)", "success": False}
        return {
            "exit_code": proc.returncode,
            "stdout": stdout_b.decode("utf-8", errors="replace"),
            "stderr": stderr_b.decode("utf-8", errors="replace"),
            "success": proc.returncode == 0,
        }
    except FileNotFoundError:
        return {"exit_code": -1, "stdout": "", "stderr": "(command not found)", "success": False}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": f"(error: {e})", "success": False}


def _extract_query(error_text: str, error_types: list[str]) -> str:
    lines = error_text.strip().split('\n')
    query_lines = [l for l in lines if l.strip() and not l.startswith(('Traceback', '  File', '    ', 'File ', 'at '))]
    return (query_lines[-1] if query_lines else error_text[:200])[:200]


async def _search_references(error_text: str, error_types: list[str]) -> str:
    """Search ALL reference sources in parallel: web, GitHub, Stack Overflow."""
    query = _extract_query(error_text, error_types)
    search_query = f"{' '.join(error_types)} {query}"
    parts = []

    async def _wrap(coro, label: str):
        try:
            result = await coro
            if result and not result.startswith("("):
                return f"\n[{label}]\n{result}"
        except Exception:
            pass
        return ""

    tasks = [
        _wrap(search_web(search_query, max_results=3), "Web"),
        _wrap(search_issues(search_query, max_results=3), "GitHub Issues"),
        _wrap(search_stackoverflow(search_query, max_results=3), "Stack Overflow"),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, str) and r:
            parts.append(r)

    return "\n".join(parts)


# ── Error Knowledge Base (async) ─────────────────────────────────────────


async def _save_to_kb(entry: dict, cwd: str = "") -> str:
    kb_dir = _resolve_kb_dir(cwd) if cwd else _resolve_kb_dir()
    await asyncio.to_thread(kb_dir.mkdir, parents=True, exist_ok=True)
    ts = entry.get("timestamp", datetime.now().isoformat())
    safe_ts = ts.replace(":", "-").replace(".", "-")
    fname = f"error_{safe_ts}.json"
    fpath = kb_dir / fname
    try:
        data = json.dumps(entry, indent=2, ensure_ascii=False)
        await asyncio.to_thread(lambda: fpath.write_text(data, encoding="utf-8"))
        vec_ok = await _save_to_vector(entry)
        result = str(fpath)
        if vec_ok:
            result += " (vector indexed)"
        return result
    except Exception as e:
        return f"(save failed: {e})"


async def _search_kb_file(query: str, limit: int = 5) -> list[dict]:
    kb_dir = _resolve_kb_dir()
    await asyncio.to_thread(kb_dir.mkdir, parents=True, exist_ok=True)
    q_lower = query.lower()
    results = []

    def _scan() -> list[dict]:
        out = []
        files = sorted(kb_dir.glob("error_*.json"), reverse=True)
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    entry = json.load(fh)
            except Exception:
                continue
            score = 0
            for val in entry.values():
                if isinstance(val, str) and q_lower in val.lower():
                    score += 1
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, str) and q_lower in v.lower():
                            score += 1
            if score > 0:
                out.append((score, entry))
        out.sort(key=lambda x: -x[0])
        return [e for _, e in out[:limit]]

    return await asyncio.to_thread(_scan)


async def _search_kb(query: str, limit: int = 5) -> list[dict]:
    vec_results = await _vector_search_kb(query, limit=limit, min_score=0.0)
    if vec_results:
        out = []
        for vr in vec_results:
            meta = vr.get("metadata", {})
            entry = {
                "timestamp": vr.get("id", "?")[:19],
                "command": meta.get("command", ""),
                "fixes": meta.get("fixes", []),
                "error_types": meta.get("error_types", []),
                "error_message": vr.get("text", ""),
                "project": meta.get("project", ""),
                "_score": vr.get("score", 0),
                "_source": "vector",
            }
            out.append(entry)
        if out:
            return out
    file_results = await _search_kb_file(query, limit=limit)
    for r in file_results:
        r["_source"] = "keyword"
    return file_results


async def _kb_stats() -> dict:
    kb_dir = _resolve_kb_dir()
    await asyncio.to_thread(kb_dir.mkdir, parents=True, exist_ok=True)

    def _scan() -> dict:
        total = 0
        by_type: dict[str, int] = {}
        by_project: dict[str, int] = {}
        for f in kb_dir.glob("error_*.json"):
            total += 1
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    e = json.load(fh)
                for et in e.get("error_types", []):
                    by_type[et] = by_type.get(et, 0) + 1
                proj = e.get("project", "?")
                by_project[proj] = by_project.get(proj, 0) + 1
            except Exception:
                pass
        return {
            "total": total,
            "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])[:10]),
            "by_project": dict(sorted(by_project.items(), key=lambda x: -x[1])[:10]),
        }

    return await asyncio.to_thread(_scan)


# ── Vector integration (pgvector) — async wrappers ───────────────────────

_VECTOR_COLLECTION = "error_kb"
_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_EMBEDDING_DIM = int(os.environ.get("VECTOR_EMBEDDING_DIM", "1536"))


async def _embed_text(text: str) -> list[float] | None:
    """Embed text using OpenAI API. Runs in thread to avoid blocking event loop."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = await asyncio.to_thread(
            client.embeddings.create,
            model=os.environ.get("VECTOR_EMBEDDING_MODEL", "text-embedding-3-small"),
            input=[text],
        )
        return r.data[0].embedding
    except Exception:
        return None


_VECTOR_CONN = None
_VECTOR_TABLE_INIT = False


def _vector_conn() -> Any:
    global _VECTOR_CONN
    if _VECTOR_CONN is None:
        import psycopg2
        if not _DATABASE_URL:
            raise ValueError("DATABASE_URL not set")
        _VECTOR_CONN = psycopg2.connect(_DATABASE_URL)
        _VECTOR_CONN.autocommit = True
    return _VECTOR_CONN


def _vec_table() -> str:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', _VECTOR_COLLECTION)
    return f"vec_{safe}"


def _ensure_vector_table() -> None:
    global _VECTOR_TABLE_INIT
    if _VECTOR_TABLE_INIT:
        return
    conn = _vector_conn()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    tbl = _vec_table()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {tbl} (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            metadata JSONB DEFAULT '{{}}',
            embedding vector({_EMBEDDING_DIM}),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute(f"CREATE INDEX IF NOT EXISTS {tbl}_idx ON {tbl} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    cur.close()
    _VECTOR_TABLE_INIT = True


async def _save_to_vector(entry: dict) -> bool:
    if not _DATABASE_URL:
        return False

    def _sync() -> bool:
        try:
            text = f"{' '.join(entry.get('error_types', []))} {entry.get('error_message', '')} {entry.get('command', '')}"
            emb = _embed_text_sync(text)
            if emb is None:
                return False
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            _ensure_vector_table()
            tbl = _vec_table()
            doc_id = entry.get("timestamp", datetime.now().isoformat())
            meta = json.dumps({
                "command": entry.get("command", ""),
                "fixes": entry.get("fixes", []),
                "error_types": entry.get("error_types", []),
                "project": entry.get("project", ""),
            })
            conn = _vector_conn()
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {tbl} (id, text, metadata, embedding)
                VALUES (%s, %s, %s::jsonb, %s::vector)
                ON CONFLICT (id) DO UPDATE
                SET text=EXCLUDED.text, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding
            """, (doc_id, text, meta, emb_str))
            cur.close()
            return True
        except Exception:
            return False

    return await asyncio.to_thread(_sync)


async def _vector_search_kb(query: str, limit: int = 5, min_score: float = 0.0) -> list[dict]:
    if not _DATABASE_URL:
        return []

    def _sync() -> list:
        try:
            qvec = _embed_text_sync(query)
            if qvec is None:
                return []
            emb_str = "[" + ",".join(str(v) for v in qvec) + "]"
            _ensure_vector_table()
            tbl = _vec_table()
            conn = _vector_conn()
            cur = conn.cursor()
            cur.execute(f"""
                SELECT id, text, metadata, 1 - (embedding <=> %s::vector) AS score
                FROM {tbl}
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY score DESC
                LIMIT %s
            """, (emb_str, emb_str, min_score, limit))
            rows = cur.fetchall()
            cur.close()
            results = []
            for row in rows:
                meta = row[2] if isinstance(row[2], dict) else json.loads(row[2]) if row[2] else {}
                results.append({
                    "id": row[0],
                    "text": (meta.get("error_types", []) or ["?"])[0] + ": " + (row[1] or "")[:200],
                    "score": round(float(row[3]), 4),
                    "metadata": meta,
                })
            return results
        except Exception:
            return []

    return await asyncio.to_thread(_sync)


def _embed_text_sync(text: str) -> list[float] | None:
    """Sync embedding call — runs inside asyncio.to_thread."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.embeddings.create(
            model=os.environ.get("VECTOR_EMBEDDING_MODEL", "text-embedding-3-small"),
            input=[text],
        )
        return r.data[0].embedding
    except Exception:
        return None


# ── Trend analysis (async) ──────────────────────────────────────────────


async def _kb_trends(days: int = 30) -> dict:
    kb_dir = _resolve_kb_dir()
    await asyncio.to_thread(kb_dir.mkdir, parents=True, exist_ok=True)
    cutoff = time.time() - days * 86400

    def _scan() -> list:
        entries = []
        for f in kb_dir.glob("error_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    e = json.load(fh)
                ts_str = e.get("timestamp", "")
                if ts_str:
                    try:
                        dt = datetime.fromisoformat(ts_str)
                        if dt.timestamp() < cutoff:
                            continue
                    except Exception:
                        pass
                entries.append(e)
            except Exception:
                pass
        return entries

    entries = await asyncio.to_thread(_scan)

    if not entries:
        return {"total": 0, "period_days": days, "by_type": {}, "by_date": {}, "by_project": {}, "fix_rate": 0.0}

    by_type: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_date: dict[str, int] = {}
    total_fixed = 0

    for e in entries:
        for et in e.get("error_types", []):
            by_type[et] = by_type.get(et, 0) + 1
        proj = e.get("project", "")
        if proj:
            by_project[proj] = by_project.get(proj, 0) + 1
        ts = e.get("timestamp", "")
        if ts:
            day = ts[:10]
            by_date[day] = by_date.get(day, 0) + 1
        if e.get("fixes"):
            total_fixed += 1

    return {
        "total": len(entries),
        "period_days": days,
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "by_project": dict(sorted(by_project.items(), key=lambda x: -x[1])),
        "by_date": dict(sorted(by_date.items())),
        "fix_rate": round(total_fixed / len(entries), 3) if entries else 0.0,
    }


@mcp.tool(
    name="autofix_run",
    description=(
        "Run a command, auto-detect errors, apply fixes, retry, and optionally commit. "
        "Supports pip install for ImportError, npm install for JS.ModuleNotFound, "
        "and general fix suggestions for other errors. "
        "When no auto-fix strategy exists, automatically searches web, GitHub, "
        "and Stack Overflow for the error message. Saves failed errors to knowledge "
        "base (error_kb/) for future reference. Checks KB for similar past errors. "
        "Returns full debug log."
    ),
)
async def autofix_run(
    command: str,
    workdir: str = "",
    max_retries: int = MAX_RETRIES_DEFAULT,
    auto_commit: bool = False,
    commit_message: str = "",
) -> str:
    cwd = workdir or os.getcwd()
    lines = [
        f"── autofix_run: {command!r} ──",
        f"CWD       : {cwd}",
        f"Max retries: {max_retries}",
    ]

    _DANGEROUS_PATTERNS = [
        (r'\brm\s+-[rf]+\b', "rm -rf recursive delete"),
        (r'\bRemove-Item\b.*-Recurse', "PowerShell recursive delete"),
        (r'\brd\s+/[sS]\s+/[qQ]\b', "rd /s /q recursive delete"),
        (r'\b(shutdown|Stop-Computer)\b', "system shutdown"),
        (r'\b(del|erase|Remove-Item)\b.*/([fs]|Force)', "forced file delete"),
        (r'format\s+\w:', "drive format"),
        (r':\(\)\s*\{|:\(\)\s*\|', "bash fork bomb"),
        (r'>\s*/dev/\w+', "destructive redirect"),
        (r'\b(dd|mkfs|fdisk)\b', "disk write command"),
    ]
    for pattern, desc in _DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"(blocked: command contains dangerous pattern '{desc}')"

    attempt = 0
    applied_fixes = []

    while attempt <= max_retries:
        if attempt > 0:
            lines.append(f"\n── Retry #{attempt} ──")

        result = await _run_shell(command, cwd, timeout=120)
        exit_code = result["exit_code"]
        stdout = result["stdout"]
        stderr = result["stderr"]

        if exit_code == 0:
            lines.append(f"\n✅ Command succeeded (exit code 0)")
            if stdout.strip():
                lines.append(f"\n[stdout]\n{stdout[:2000]}")
            if stderr.strip():
                lines.append(f"\n[stderr]\n{stderr[:1000]}")

            if auto_commit and applied_fixes:
                msg = commit_message or f"autofix: {', '.join(applied_fixes)}"
                safe_msg = shlex.quote(msg)
                try:
                    git_proc = await _run_shell(
                        f'git commit -a -m {safe_msg}',
                        cwd=cwd, timeout=30
                    )
                    if git_proc["success"]:
                        lines.append(f"\n✅ Committed: {msg}")
                    else:
                        lines.append(f"\nℹ️  Git commit skipped: {git_proc['stderr'][:200]}")
                except Exception:
                    lines.append("\nℹ️  Git commit failed (not a git repo?)")

            _record({
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "success": True,
                "attempts": attempt,
                "fixes": applied_fixes,
                "error_types": [],
            })
            return "\n".join(lines)

        error_text = stderr + "\n" + stdout
        lang = _auto_detect_language(error_text)

        parsers = {
            "python": _parse_python_traceback,
            "nodejs": _parse_node_traceback,
            "rust": _parse_rust_traceback,
        }
        parser = parsers.get(lang, _parse_python_traceback)
        parsed = parser(error_text)
        error_types = _classify(error_text)

        lines.append(f"\n❌ Exit code: {exit_code}")
        if parsed.get("error_type"):
            lines.append(f"   Error type: {parsed['error_type']}")
        if parsed.get("error_message"):
            lines.append(f"   Message: {parsed['error_message'][:200]}")
        lines.append(f"   Classifications: {', '.join(error_types)}")

        if attempt == 0:
            kb_results = await _search_kb(" ".join(error_types), limit=3)
            if kb_results:
                lines.append(f"\n📚 Found {len(kb_results)} similar error(s) in knowledge base:")
                for i, kb in enumerate(kb_results, 1):
                    ts = kb.get("timestamp", "")[:19]
                    cmd = kb.get("command", "")[:60]
                    kb_fixes = kb.get("fixes", [])
                    kb_str = ", ".join(kb_fixes) if kb_fixes else "no fix found"
                    lines.append(f"  {i}. [{ts}] {cmd}")
                    lines.append(f"     Fixes: {kb_str}")

        if attempt >= max_retries:
            lines.append(f"\n⚠️  Max retries ({max_retries}) reached. Searching references...")
            refs = await _search_references(error_text, error_types)
            if refs:
                lines.append(refs)
            lines.append(f"\n⚠️  Manual debugging needed after all retries.")
            break

        fix_cmds = _build_fix_commands(error_types, error_text, cwd)

        if fix_cmds:
            for fix_cmd, fix_desc in fix_cmds:
                lines.append(f"\n🛠  {fix_desc}")
                lines.append(f"    $ {fix_cmd}")
                fix_result = await _run_shell(fix_cmd, cwd, timeout=120)
                if fix_result["success"]:
                    lines.append(f"   ✅ Fix succeeded")
                    applied_fixes.append(fix_desc)
                else:
                    err = fix_result["stderr"][:200]
                    lines.append(f"   ⚠️  Fix failed: {err}")
        else:
            suggestions = []
            for et in error_types:
                if et in FIX_SUGGESTIONS:
                    suggestions.append(f"  [{et}] {FIX_SUGGESTIONS[et]}")
            if suggestions:
                lines.append(f"\n💡 No automatic fix available. Suggestions:")
                lines.extend(suggestions)

            lines.append(f"\n🔍 Searching all references (web, GitHub, Stack Overflow)...")
            refs = await _search_references(error_text, error_types)
            if refs:
                lines.append(refs)
            else:
                lines.append(f"   (no relevant references found)")

            lines.append(f"\n⚠️  Cannot auto-fix this error. Use search results above as reference.")
            break

        attempt += 1

    _record({
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "success": False,
        "attempts": attempt,
        "fixes": applied_fixes,
        "error_types": error_types,
        "error_text": error_text[:500],
        "project": cwd,
    })

    if not _STATELESS:
        kb_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "success": False,
            "attempts": attempt,
            "fixes": applied_fixes,
            "error_types": error_types,
            "error_message": (parsed.get("error_message") or error_text[:300]),
            "error_text_tail": error_text[:1000],
            "project": cwd,
        }
        saved_path = await _save_to_kb(kb_entry, cwd=cwd)
        lines.append(f"\n💾 Error saved to knowledge base: {saved_path}")

    if stderr.strip():
        lines.append(f"\n[stderr tail]\n{stderr[:2000]}")
    if stdout.strip() and not stderr.strip():
        lines.append(f"\n[stdout tail]\n{stdout[:1000]}")

    return "\n".join(lines)


@mcp.tool(
    name="autofix_history",
    description="Show auto-fix session history: all commands, fixes applied, and outcomes.",
)
async def autofix_history(limit: int = 10) -> str:
    if not _autofix_history:
        return "(no autofix sessions yet)"

    entries = _autofix_history[-limit:]
    lines = [f"── Auto-Fix History (last {len(entries)}/{len(_autofix_history)}) ──\n"]
    for i, e in enumerate(reversed(entries), 1):
        etypes = ", ".join(e.get("error_types", [])) if not e.get("success") else ""
        lines.append(
            f"{i:2d}. [{e['timestamp'][11:19]}] {'✅' if e['success'] else '❌'} "
            f"{e['command'][:60]}\n"
            f"     Attempts: {e['attempts']}, Fixes: {e.get('fixes', [])}"
            f"{f', Types: {etypes}' if etypes else ''}\n"
        )
    return "\n".join(lines)


@mcp.tool(
    name="autofix_strategies",
    description="List all supported auto-fix strategies and their descriptions.",
)
async def autofix_strategies() -> str:
    lines = ["── Auto-Fix Strategies ──\n"]
    for etype, desc in sorted(FIX_STRATEGIES_DESC.items()):
        lines.append(f"  {etype}: {desc}")
    lines.append("\n── Other Errors (suggestions only) ──\n")
    for etype, suggestion in sorted(FIX_SUGGESTIONS.items()):
        if etype not in FIX_STRATEGIES_DESC:
            lines.append(f"  {etype}: {suggestion}")
    return "\n".join(lines)


@mcp.tool(
    name="autofix_save_error",
    description="Simpan error manual ke knowledge base untuk referensi session mendatang."
)
async def autofix_save_error(
    error_message: str,
    error_types: str = "",
    command: str = "",
    context: str = "",
    project: str = "",
) -> str:
    entry = {
        "timestamp": datetime.now().isoformat(),
        "command": command or "",
        "success": False,
        "attempts": 0,
        "fixes": [],
        "error_types": [et.strip() for et in error_types.split(",") if et.strip()] or ["Unknown"],
        "error_message": error_message,
        "error_text_tail": context[:1000] or error_message[:1000],
        "project": project or os.getcwd(),
    }
    path = await _save_to_kb(entry, cwd=project or os.getcwd())
    return f"✅ Error saved to knowledge base: {path}"


@mcp.tool(
    name="autofix_search_kb",
    description="Cari error serupa di knowledge base (error_kb/)."
    " Menggunakan vector search (semantic) jika DATABASE_URL terkonfigurasi,"
    " fallback keyword search jika tidak."
)
async def autofix_search_kb(query: str, limit: int = 5) -> str:
    results = await _search_kb(query, limit=limit)
    if not results:
        return "(no matching errors in knowledge base)"

    out = [f"── Knowledge Base Search: {query!r} (found {len(results)}) ──\n"]
    for i, e in enumerate(results, 1):
        ts = e.get("timestamp", "?")[:19]
        cmd = e.get("command", "?")[:80]
        emsg = e.get("error_message", "")[:150]
        etypes = ", ".join(e.get("error_types", []))
        fixes = ", ".join(e.get("fixes", [])) or "—"
        proj = e.get("project", "?")
        source = e.get("_source", "keyword")
        score = e.get("_score", "")
        score_str = f" (score: {score})" if score else ""
        out.append(
            f"{i}. [{ts}] {cmd}\n"
            f"   Types: {etypes} [{source}{score_str}]\n"
            f"   Error: {emsg}\n"
            f"   Fixes: {fixes}\n"
            f"   Project: {proj}\n"
        )
    return "\n".join(out)


@mcp.tool(
    name="autofix_kb_stats",
    description="Lihat statistik knowledge base: total error, error types, project."
)
async def autofix_kb_stats() -> str:
    stats = await _kb_stats()
    total = stats["total"]
    if total == 0:
        return "(knowledge base is empty — errors will be saved automatically when autofix_run fails)"

    out = [
        f"── Knowledge Base Stats ──",
        f"Total errors saved: {total}\n",
        "Top Error Types:",
    ]
    for etype, count in stats["by_type"].items():
        out.append(f"  {etype}: {count}x")
    out.append("")
    out.append("Top Projects:")
    for proj, count in stats["by_project"].items():
        out.append(f"  {proj}: {count}x")
    return "\n".join(out)


@mcp.tool(
    name="autofix_kb_trends",
    description="Multi-session error trend dashboard. Lihat frekuensi error per-tipe, per-project, per-hari,"
    " dan fix success rate dalam periode tertentu."
)
async def autofix_kb_trends(days: int = 30, top_n: int = 10) -> str:
    trends = await _kb_trends(days=days)
    total = trends["total"]
    if total == 0:
        return f"(no errors in the last {days} days)"

    out = [
        f"── Error Trends (last {days}d) ──",
        f"Total errors: {total}",
        f"Fix rate    : {trends['fix_rate']*100:.1f}%",
        f"Period     : {trends['period_days']} days\n",
        "By Error Type:",
    ]

    for et, cnt in list(trends["by_type"].items())[:top_n]:
        bar = "█" * min(cnt, 30)
        out.append(f"  {et:35s} {bar} {cnt}")
    out.append("")

    if trends["by_project"]:
        out.append("By Project:")
        for proj, cnt in list(trends["by_project"].items())[:top_n]:
            bar = "█" * min(cnt, 30)
            out.append(f"  {proj:35s} {bar} {cnt}")
        out.append("")

    if trends["by_date"]:
        out.append("By Date:")
        dates = list(trends["by_date"].items())
        for day, cnt in dates[-14:]:
            bar = "█" * min(cnt, 20)
            out.append(f"  {day} {bar} {cnt}")
        out.append("")

    out.append(f"(use vector search — set DATABASE_URL for semantic similarity)")
    return "\n".join(out)


# ── Code Analysis Fix Integration ────────────────────────────────────────────

_IMPORT_PKG_RE = re.compile(r"(?:No module named|ImportError)\s*['\"]?([a-zA-Z0-9_.-]+)")


@mcp.tool(name="fix_lint_errors",
          description="Accept pylint/code-analyzer findings JSON, auto-fix import errors via pip install, return retry-ready result.")
async def fix_lint_errors(
    lint_result_json: str,
    max_fixes: int = 10,
    retry_command: str = "",
) -> str:
    """
    Accept lint findings (JSON array or result dict from pylint.lint_file),
    detect fixable errors (E0401 import, E0602 undefined, C0415 outside-toplevel),
    apply pip install for each missing package, return updated findings + fix log.

    Usage:
        result = await fix_lint_errors(lint_result)
        # retry_command will be executed after fixes applied
    """
    try:
        data = json.loads(lint_result_json)
        findings = data if isinstance(data, list) else data.get("findings", [])
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False)

    fixes = []
    fixed_ids = set()
    remaining = []

    for f in findings:
        msg_id = f.get("message-id", "")
        msg = f.get("message", "")
        path = f.get("file", f.get("path", ""))

        if msg_id in ("E0401",) and msg_id not in fixed_ids:
            match = _IMPORT_PKG_RE.search(msg)
            if match:
                pkg = match.group(1)
                if len(fixes) < max_fixes:
                    fix_key = f"pip install {pkg}"
                    if fix_key not in fixed_ids:
                        fixed_ids.add(fix_key)
                        # Try to install directly
                        try:
                            import subprocess as _sp
                            import sys as _sys
                            _r = _sp.run([_sys.executable, "-m", "pip", "install", pkg],
                                          capture_output=True, text=True, timeout=60)
                            success = _r.returncode == 0
                            fixes.append({
                                "package": pkg,
                                "command": fix_key,
                                "source_path": path,
                                "source_line": f.get("line", 0),
                                "message_id": msg_id,
                                "success": success,
                                "detail": _r.stdout.strip()[:200] if success else _r.stderr.strip()[:200],
                            })
                        except Exception as ex:
                            fixes.append({
                                "package": pkg,
                                "command": fix_key,
                                "success": False,
                                "error": str(ex),
                            })
                        continue
            remaining.append(f)
        elif msg_id in ("E0602", "W0611", "C0415"):
            remaining.append({
                **f,
                "fix_hint": {
                    "E0602": "Add import or check variable name spelling",
                    "W0611": "Remove unused import or use the imported name",
                    "C0415": "Move import to top of file",
                }.get(msg_id, "Manual fix required"),
                "auto_fixable": False,
            })
            remaining.append(f)
        else:
            remaining.append(f)

    return json.dumps({
        "fixes_applied": fixes,
        "fix_count": len(fixes),
        "remaining_count": len(remaining),
        "remaining_findings": remaining,
        "auto_fixable_remaining": sum(1 for r in remaining
                                       if r.get("message-id") in ("E0401", "E0602", "W0611", "C0415")),
        "retry_command": retry_command if retry_command else "",
    }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
