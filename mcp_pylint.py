"""
mcp_pylint.py — Pylint Linting MCP Server
==========================================
Run pylint on Python files/projects, parse results, and return structured findings.
Supports custom config, parallel execution, and integration with autofix.

References:
- Pylint MCP by Matthew Sayer: https://medium.com/@matthew.sayer1/checking-code-quality-with-ai-mcp-and-pylint-7b4cf59ee16c
- mcp_python_toolbox: https://github.com/gianlucamazza/mcp_python_toolbox
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pylint", instructions="""
Pylint static analysis for Python code.
Run linting on files or projects, get structured findings with severity,
line numbers, and fix suggestions.

Tools:
- lint_file: Lint single Python file
- lint_project: Lint entire project (respects .pylintrc)
- lint_string: Lint code from string (temp file)
- get_pylint_version: Check pylint version
- parse_pylint_output: Parse raw pylint JSON/text output
- suggest_fixes: Get fix suggestions for common pylint messages
""")


# ── Helpers ──────────────────────────────────────────────────────────────────

_PYLINT_AVAILABLE = False
_PYLINT_VERSION = ""

try:
    result = subprocess.run(
        [sys.executable, "-m", "pylint", "--version"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        _PYLINT_AVAILABLE = True
        _PYLINT_VERSION = result.stdout.strip().split("\n")[0]
except Exception:
    pass


def _run_pylint(args: List[str], cwd: str = "") -> dict:
    """Run pylint and return structured result."""
    if not _PYLINT_AVAILABLE:
        return {"error": "pylint not installed. Run: pip install pylint", "success": False}

    cmd = [sys.executable, "-m", "pylint"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd or None
        )
        return {
            "success": result.returncode in (0, 1, 2, 4, 8, 16, 32),  # pylint exit codes
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"error": "pylint timeout (120s)", "success": False}
    except Exception as e:
        return {"error": f"pylint execution failed: {e}", "success": False}


def _parse_pylint_json(output: str) -> List[dict]:
    """Parse pylint JSON output."""
    try:
        data = json.loads(output)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _parse_pylint_text(output: str) -> List[dict]:
    """Parse pylint text output (fallback)."""
    findings = []
    for line in output.splitlines():
        # Format: file:line:col: msg_id: message (symbol)
        parts = line.split(":", 4)
        if len(parts) >= 5:
            try:
                findings.append({
                    "path": parts[0],
                    "line": int(parts[1]),
                    "column": int(parts[2]),
                    "message_id": parts[3].strip(),
                    "message": parts[4].strip(),
                    "symbol": "",
                })
            except ValueError:
                pass
    return findings


def _categorize_findings(findings: List[dict]) -> dict:
    """Categorize findings by severity."""
    categories = {"fatal": [], "error": [], "warning": [], "refactor": [], "convention": [], "info": []}
    for f in findings:
        msg_id = f.get("message_id", "")
        if msg_id.startswith("F"):
            categories["fatal"].append(f)
        elif msg_id.startswith("E"):
            categories["error"].append(f)
        elif msg_id.startswith("W"):
            categories["warning"].append(f)
        elif msg_id.startswith("R"):
            categories["refactor"].append(f)
        elif msg_id.startswith("C"):
            categories["convention"].append(f)
        elif msg_id.startswith("I"):
            categories["info"].append(f)
    return categories


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(name="lint_file",
          description="Run pylint on a single Python file with optional config.")
async def lint_file(
    file_path: str,
    config_file: str = "",
    enable: str = "",
    disable: str = "",
    output_format: str = "json",
) -> str:
    if not Path(file_path).exists():
        return json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)

    args = ["--output-format", output_format]
    if config_file:
        args.extend(["--rcfile", config_file])
    if enable:
        args.extend(["--enable", enable])
    if disable:
        args.extend(["--disable", disable])
    args.append(file_path)

    result = _run_pylint(args)
    if not result["success"] and "error" in result:
        return json.dumps(result, ensure_ascii=False)

    findings = _parse_pylint_json(result["stdout"]) if output_format == "json" else _parse_pylint_text(result["stdout"])
    categories = _categorize_findings(findings)

    return json.dumps({
        "file": file_path,
        "returncode": result["returncode"],
        "total_findings": len(findings),
        "categories": {k: len(v) for k, v in categories.items()},
        "findings": findings,
    }, ensure_ascii=False)


@mcp.tool(name="lint_project",
          description="Run pylint on entire project (discovers .py files, uses .pylintrc if present).")
async def lint_project(
    root_dir: str = ".",
    config_file: str = "",
    max_files: int = 100,
    output_format: str = "json",
    ignore_patterns: List[str] = None,
) -> str:
    root = Path(root_dir).resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Directory not found: {root_dir}"}, ensure_ascii=False)

    py_files = []
    for p in root.rglob("*.py"):
        if any(p.match(pattern) for pattern in (ignore_patterns or ["**/__pycache__/**", "**/.venv/**", "**/venv/**", "**/env/**", "**/node_modules/**", "**/.git/**"])):
            continue
        py_files.append(p)
        if len(py_files) >= max_files:
            break

    if not py_files:
        return json.dumps({"error": "No Python files found"}, ensure_ascii=False)

    args = ["--output-format", output_format, "--recursive=y"]
    if config_file:
        args.extend(["--rcfile", config_file])
    args.append(str(root))

    result = _run_pylint(args, cwd=str(root))
    if not result["success"] and "error" in result:
        return json.dumps(result, ensure_ascii=False)

    findings = _parse_pylint_json(result["stdout"]) if output_format == "json" else _parse_pylint_text(result["stdout"])
    categories = _categorize_findings(findings)

    by_file = {}
    for f in findings:
        path = f.get("path", "")
        by_file.setdefault(path, []).append(f)

    return json.dumps({
        "root": str(root),
        "files_scanned": len(py_files),
        "total_findings": len(findings),
        "categories": {k: len(v) for k, v in categories.items()},
        "by_file": {k: len(v) for k, v in by_file.items()},
        "findings": findings,
    }, ensure_ascii=False)


@mcp.tool(name="lint_string",
          description="Lint Python code from a string (writes to temp file).")
async def lint_string(
    code: str,
    config_file: str = "",
    output_format: str = "json",
) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = await lint_file(temp_path, config_file, output_format=output_format)
        return result
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@mcp.tool(name="get_pylint_version",
          description="Get pylint version and availability.")
async def get_pylint_version() -> str:
    return json.dumps({
        "available": _PYLINT_AVAILABLE,
        "version": _PYLINT_VERSION,
        "python": sys.version.split()[0],
    }, ensure_ascii=False)


@mcp.tool(name="parse_pylint_output",
          description="Parse raw pylint output (JSON or text) into structured findings.")
async def parse_pylint_output(output: str, format: str = "json") -> str:
    findings = _parse_pylint_json(output) if format == "json" else _parse_pylint_text(output)
    categories = _categorize_findings(findings)
    return json.dumps({
        "total_findings": len(findings),
        "categories": {k: len(v) for k, v in categories.items()},
        "findings": findings,
    }, ensure_ascii=False)


@mcp.tool(name="suggest_fixes",
          description="Get fix suggestions for common pylint message IDs.")
async def suggest_fixes(message_ids: List[str]) -> str:
    """Common pylint message fix suggestions."""
    suggestions = {
        "C0114": "Add module docstring at top of file: \"\"\"Module description.\"\"\"",
        "C0115": "Add class docstring: \"\"\"Class description.\"\"\"",
        "C0116": "Add function/method docstring: \"\"\"Function description.\"\"\"",
        "C0301": "Line too long — break into multiple lines or increase max-line-length in config",
        "C0303": "Trailing whitespace — remove spaces at end of line",
        "C0304": "Missing final newline — add newline at end of file",
        "W0611": "Unused import — remove or use the imported name",
        "W0612": "Unused variable — remove or prefix with _",
        "W0613": "Unused argument — prefix with _ or use it",
        "W0621": "Redefining outer name — rename inner variable",
        "W0707": "Raise from cause — use 'raise NewError from original_error'",
        "R0903": "Too few public methods — consider adding methods or using a function",
        "R0913": "Too many arguments — use dataclass, namedtuple, or **kwargs",
        "R0914": "Too many local variables — refactor into smaller functions",
        "R0915": "Too many statements — split function",
        "R1705": "Unnecessary else after return — remove else block",
        "E1101": "Member not found — check attribute name or add type hints",
        "E0602": "Undefined variable — check spelling or add import",
        "E0401": "Import error — install missing package or fix import path",
    }

    result = {}
    for msg_id in message_ids:
        result[msg_id] = suggestions.get(msg_id, "No suggestion available. Check pylint docs: https://pylint.pycqa.org/")
    return json.dumps({"suggestions": result}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
