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


@mcp.tool(
    name="autofix_run",
    description=(
        "Run a command, auto-detect errors, apply fixes, retry, and optionally commit. "
        "Supports pip install for ImportError, npm install for JS.ModuleNotFound, "
        "and general fix suggestions for other errors. Returns full debug log."
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

        if attempt >= max_retries:
            lines.append(f"\n⚠️  Max retries ({max_retries}) reached. Manual debugging needed.")
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
            # No auto-fix strategy — give suggestion
            suggestions = []
            for et in error_types:
                if et in FIX_SUGGESTIONS:
                    suggestions.append(f"  [{et}] {FIX_SUGGESTIONS[et]}")
            if suggestions:
                lines.append(f"\n💡 No automatic fix available. Suggestions:")
                lines.extend(suggestions)
            lines.append(f"\n⚠️  Cannot auto-fix this error. Manual debugging required.")
            break

        attempt += 1

    _record({
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "success": False,
        "attempts": attempt,
        "fixes": applied_fixes,
        "error_types": error_types,
    })

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
        lines.append(
            f"{i:2d}. [{e['timestamp'][11:19]}] {'✅' if e['success'] else '❌'} "
            f"{e['command'][:60]}\n"
            f"     Attempts: {e['attempts']}, Fixes: {e.get('fixes', [])}\n"
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
