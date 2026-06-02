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
import json
import os
import re
import sys
import shlex
from pathlib import Path
from datetime import datetime
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

mcp = FastMCP(
    "autofix",
    instructions=(
        "Auto-fix server. Run a command, detect errors, apply fixes automatically, "
        "retry, and optionally commit. Use autofix_run whenever a command fails — "
        "this server will parse the error, classify it, apply the correct fix "
        "(pip install, npm install, etc.), and retry. You MUST use this instead of "
        "manually debugging. Only manual debugging if autofix_run fails after all "
        "retries."
    ),
)

MAX_RETRIES_DEFAULT = 3

_STATELESS = os.environ.get("AUTOFIX_STATELESS", "0") == "1"
_ERROR_KB_DIR = Path(os.environ.get("ERROR_KB_DIR", Path(__file__).parent / "error_kb"))

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


def _h_black_format(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    # Extract file path from last traceback frame
    frame_m = re.search(r'File "([^"]+)", line \d+', error_text)
    if frame_m:
        file_path = frame_m.group(1)
        return [(f"black \"{file_path}\"", f"Format '{file_path}' with black")]
    return [("black .", "Format all Python files with black")]


def _h_ping_db(error_types: list[str], error_text: str, cwd: str) -> list[tuple[str, str]]:
    # Try a simple connectivity check
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
}

FIX_STRATEGIES_DESC = {
    "Python.ImportError": "pip install <package> (auto-extract)",
    "Python.ModuleNotFoundError": "pip install <package> (auto-extract)",
    "JS.ModuleNotFound": "npm install <package> (auto-extract)",
    "Python.FileNotFound": "mkdir parent directory (auto-extract path)",
    "JS.ENOENT": "mkdir parent directory (auto-extract path)",
    "JS.EADDRINUSE": "netstat + taskkill / lsof -ti:PORT | kill (auto-extract port)",
    "Go.BuildError": "go mod tidy",
    "Python.IndentationError": "black <file> (auto-extract file from traceback)",
}

FIX_SUGGESTIONS = {
    "Python.ImportError": "Missing Python package. Use pip install <package>.",
    "Python.ModuleNotFoundError": "Missing Python module. Use pip install <package>.",
    "JS.ModuleNotFound": "Missing npm package. Use npm install <package>.",
    "Python.SyntaxError": "Check for missing brackets, colons, or indentation.",
    "Python.IndentationError": "Fix indentation — mix of tabs/spaces.",
    "Python.NameError": "Check variable/function name for typos.",
    "Python.TypeError": "Check types — use type() or isinstance().",
    "Python.AttributeError": "Check attribute name or None object.",
    "Python.FileNotFound": "Check file path and current working directory.",
    "Python.KeyError": "Use dict.get(key) instead of dict[key].",
    "Python.IndexError": "Check list length before accessing index.",
    "Python.ValueError": "Check input value and type conversion.",
    "Python.RuntimeError": "Generic runtime error — read full traceback.",
    "Python.RecursionError": "Add base case or switch to iteration.",
    "Python.MemoryError": "Reduce data in memory or process in batches.",
    "Python.PermissionError": "Run as admin or check file permissions.",
    "Python.TimeoutError": "Increase timeout or optimize operation.",
    "Python.AssertionError": "Check asserted condition.",
    "Python.ZeroDivision": "Add denominator check.",
    "JS.ReferenceError": "Check variable declaration (let/const/var).",
    "JS.TypeError": "Check for undefined/null before access.",
    "JS.SyntaxError": "Check brackets, commas, or keywords.",
    "JS.UnhandledRejection": "Add .catch() or async/await try block.",
    "JS.ENOENT": "Check file path.",
    "JS.EACCES": "Check permissions.",
    "JS.EADDRINUSE": "Change port or kill existing process.",
    "Rust.Panic": "Read panic message for location and cause.",
    "Rust.CompileError": "Check error code at doc.rust-lang.org.",
    "Rust.BorrowError": "Fix ownership and lifetimes.",
    "Go.Panic": "Read stack trace for panic location.",
    "Go.BuildError": "Check line/column in error message.",
    "DB.ConnectionError": "Ensure DB is running and connection string is correct.",
    "DB.Syntax": "Check SQL syntax and quotes.",
    "DB.UniqueViolation": "Use INSERT OR IGNORE or upsert.",
    "DB.ForeignKey": "Ensure parent data exists.",
    "General.Timeout": "Increase timeout, optimize, or check network.",
    "General.OOM": "Reduce RAM usage or use streaming.",
    "General.SegFault": "Check null/invalid memory access.",
    "General.Permission": "Check permissions or run with higher privileges.",
    "General.NetworkError": "Check internet, firewall, and server status.",
}


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


def _record(entry: dict):
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


# ── Error Knowledge Base ─────────────────────────────────────────────

def _save_to_kb(entry: dict) -> str:
    _ERROR_KB_DIR.mkdir(parents=True, exist_ok=True)
    ts = entry.get("timestamp", datetime.now().isoformat())
    safe_ts = ts.replace(":", "-").replace(".", "-")
    fname = f"error_{safe_ts}.json"
    fpath = _ERROR_KB_DIR / fname
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        return str(fpath)
    except Exception as e:
        return f"(save failed: {e})"


def _search_kb(query: str, limit: int = 5) -> list[dict]:
    _ERROR_KB_DIR.mkdir(parents=True, exist_ok=True)
    q_lower = query.lower()
    results = []
    files = sorted(_ERROR_KB_DIR.glob("error_*.json"), reverse=True)
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
            results.append((score, entry))
    results.sort(key=lambda x: -x[0])
    return [e for _, e in results[:limit]]


def _kb_stats() -> dict:
    _ERROR_KB_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    by_type: dict[str, int] = {}
    by_project: dict[str, int] = {}
    for f in _ERROR_KB_DIR.glob("error_*.json"):
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
    """
    Args:
        command: Command to run (e.g. "python app.py")
        workdir: Working directory (default: cwd)
        max_retries: Max auto-fix attempts (default: 3)
        auto_commit: If True and fix succeeds, git commit
        commit_message: Custom commit message (auto-generated if empty)
    """
    cwd = workdir or os.getcwd()
    lines = [
        f"── autofix_run: {command!r} ──",
        f"CWD       : {cwd}",
        f"Max retries: {max_retries}",
    ]

    # Safety check
    dangerous = ["rm -rf", "format ", "shutdown", "del /f", ":(){", ">("]
    for d in dangerous:
        if d.lower() in command.lower():
            return f"(blocked: command contains dangerous pattern '{d}')"

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

            # Auto-commit if requested
            if auto_commit and applied_fixes:
                msg = commit_message or f"autofix: {', '.join(applied_fixes)}"
                try:
                    git_proc = await _run_shell(
                        f'git add -A && git commit -m "{msg}"',
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

        # Command failed — parse error
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

        # Search KB for similar past errors
        if attempt == 0:
            kb_results = _search_kb(" ".join(error_types), limit=3)
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

        # Try auto-fix
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
            # No auto-fix strategy — give suggestion + search references
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

    # Auto-save failed error to KB
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
        saved_path = _save_to_kb(kb_entry)
        lines.append(f"\n💾 Error saved to knowledge base: {saved_path}")

    # Show stderr tail
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
    path = _save_to_kb(entry)
    return f"✅ Error saved to knowledge base: {path}"


@mcp.tool(
    name="autofix_search_kb",
    description="Cari error serupa di knowledge base (error_kb/). Berguna sebagai referensi cepat."
)
async def autofix_search_kb(query: str, limit: int = 5) -> str:
    results = _search_kb(query, limit=limit)
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
        out.append(
            f"{i}. [{ts}] {cmd}\n"
            f"   Types: {etypes}\n"
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
    stats = _kb_stats()
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
