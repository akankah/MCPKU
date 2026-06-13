"""
mcp_code_analyzer.py — MCP Code Analyzer Server
================================================
Static analysis, complexity metrics, dependency graphs,
security scanning, and project structure analysis.

Single-file, stdlib-first. Uses `ast` for Python parsing.
"""

import ast
import json
import os
import re
import tokenize
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("code-analyzer", instructions="""
Code analysis tools: static analysis, complexity metrics, dependency
graphs, security scanning, dead code detection, and project structure.
Works with Python files out of the box; basic analysis for JS/TS/others.

Use analyze_file() for single-file deep analysis, analyze_project()
for multi-file project overview, and security_scan() for vulnerability
pattern detection.
""")


# ── Helpers ──────────────────────────────────────────────────────────────────

_SNIPPET = re.compile(r"(?P<begin>begin\s+snippet\s+)(?P<lines>\d+-\d+)(?P<rest>[\s\S]*?)(?P<end>end\s+snippet)", re.I)

_COMMON_IGNORE = {"node_modules", ".git", "__pycache__", ".venv", "venv",
                  "env", ".tox", ".eggs", "dist", "build", ".mypy_cache",
                  ".pytest_cache", ".ruff_cache"}

_SECURITY_PATTERNS: list[tuple[str, str, str]] = [
    ("hardcoded_password", r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]", "Hardcoded password detected"),
    ("hardcoded_secret", r"(?i)(secret|api_key|apikey|token|auth_key)\s*=\s*['\"][^'\"]{8,}['\"]", "Hardcoded secret/key detected"),
    ("eval_exec", r"\b(eval|exec|compile)\s*\(", "Use of eval/exec/compile — possible code injection"),
    ("pickle_load", r"\b(pickle\.load|pickle\.loads|joblib\.load|dill\.load)\s*\(", "Unsafe deserialization — possible RCE"),
    ("sql_injection", r"(?i)(execute|executemany)\s*\(\s*f['\"]|%\(|\.format\(.*(?:WHERE|INSERT|UPDATE|DELETE)", "Possible SQL injection — use parameterized queries"),
    ("shell_injection", r"(?i)(os\.system|subprocess\.(call|Popen|run)|shutil\.which)\s*\(", "Shell execution — validate inputs"),
    ("request_without_verify", r"requests\.(get|post|put|delete|patch)\s*\(.*verify\s*=\s*False", "SSL verification disabled"),
    ("debug_enabled", r"(?i)(DEBUG|debug)\s*=\s*True", "Debug mode enabled in production code"),
    ("insecure_hash", r"\b(md5|sha1)\s*\(", "Weak hash algorithm — use SHA-256 or higher"),
    ("tmp_file", r"/tmp/|tempfile\.mktemp\(", "Possible insecure temp file — use tempfile.TemporaryFile"),
]


def _walk_files(root: str, exts: set[str] | None = None) -> list[Path]:
    root_p = Path(root).resolve()
    if not root_p.is_dir():
        return []
    files = []
    for fp in root_p.rglob("*"):
        if fp.is_dir() and fp.name in _COMMON_IGNORE:
            continue
        if fp.is_file() and (exts is None or fp.suffix in exts):
            files.append(fp)
    return files


def _safe_read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _count_lines(text: str) -> dict:
    lines = text.splitlines()
    total = len(lines)
    blank = sum(1 for l in lines if not l.strip())
    comment = 0
    in_multiline = False
    for l in lines:
        stripped = l.strip()
        if stripped.startswith("#"):
            comment += 1
        elif stripped.startswith("\"\"\"") or stripped.startswith("'''"):
            in_multiline = not in_multiline
            comment += 1
        elif in_multiline:
            comment += 1
    return {"total": total, "blank": blank, "comment": comment, "code": total - blank - comment}


def _parse_complexity(text: str) -> list[dict]:
    results = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                                      ast.ExceptHandler, ast.With, ast.AsyncWith)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
                elif isinstance(child, ast.Match):
                    complexity += len(child.cases)
            start_ln = node.lineno
            end_ln = getattr(node, "end_lineno", start_ln)
            results.append({
                "name": node.name,
                "type": "function",
                "line": start_ln,
                "end_line": end_ln,
                "complexity": complexity,
                "args": len(node.args.args),
            })

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child != node:
                    methods.append(child.name)
            start_ln = node.lineno
            end_ln = getattr(node, "end_lineno", start_ln)
            results.append({
                "name": node.name,
                "type": "class",
                "line": start_ln,
                "end_line": end_ln,
                "methods": methods,
                "bases": [b.id if isinstance(b, ast.Name) else repr(b) for b in node.bases],
            })

    return results


def _extract_imports(text: str) -> dict:
    imports: list[dict] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"imports": [], "from_imports": []}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append({
                    "module": node.module or "",
                    "name": alias.name,
                    "alias": alias.asname,
                    "level": node.level,
                    "line": node.lineno,
                })
    stdlib = _stdlib_modules()
    result = {"imports": [], "third_party": [], "local": []}
    for imp in imports:
        mod = imp.get("module", "") or imp.get("name", "")
        top = mod.split(".")[0]
        if top in stdlib:
            result["imports"].append({**imp, "type": "stdlib"})
        elif top.startswith("_"):
            result["local"].append(imp)
        else:
            result["third_party"].append(imp)
    return result


def _stdlib_modules() -> set[str]:
    return set([
        "os", "sys", "re", "json", "math", "time", "datetime", "collections",
        "itertools", "functools", "typing", "pathlib", "shutil", "glob",
        "subprocess", "threading", "multiprocessing", "socket", "http",
        "urllib", "xml", "csv", "io", "base64", "hashlib", "hmac",
        "uuid", "tempfile", "pickle", "shelve", "sqlite3", "abc",
        "argparse", "configparser", "enum", "dataclasses", "bisect",
        "copy", "decimal", "fractions", "random", "statistics",
        "textwrap", "string", "struct", "codecs", "unicodedata",
        "ast", "inspect", "dis", "traceback", "warnings", "logging",
        "pdb", "profile", "unittest", "doctest", "zipfile", "tarfile",
        "gzip", "bz2", "lzma", "ssl", "email", "html", "webbrowser",
        "tkinter", "curses", "asyncio", "signal", "platform",
        "calendar", "locale", "gettext", "optparse", "filecmp",
        "difflib", "pdb", "contextlib", "importlib", "pkgutil",
        "atexit", "gc", "inspect", "tokenize", "keyword",
    ])


def _detect_lang(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".m": "matlab",
        ".sql": "sql",
        ".sh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".xml": "xml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".less": "less",
        ".dockerfile": "dockerfile",
        ".tf": "terraform",
        ".vue": "vue",
        ".svelte": "svelte",
        ".pyx": "cython",
        ".ipynb": "jupyter",
    }.get(ext, "unknown")


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(name="analyze_file",
          description="Deep analysis of a single source file: metrics, complexity, imports, AST structure.")
async def analyze_file(file_path: str) -> str:
    path = Path(file_path).expanduser()
    if not path.is_file():
        return json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)

    text = _safe_read(path)
    if text is None:
        return json.dumps({"error": f"Cannot read file: {file_path}"}, ensure_ascii=False)

    lang = _detect_lang(path)
    lines = _count_lines(text)
    result: dict[str, Any] = {
        "file": str(path),
        "language": lang,
        "size_bytes": path.stat().st_size,
        "lines": lines,
    }

    if lang == "python":
        result["imports"] = _extract_imports(text)
        result["structure"] = _parse_complexity(text)
        high_complexity = [s for s in result["structure"]
                          if s.get("type") == "function" and s.get("complexity", 0) > 10]
        if high_complexity:
            result["warnings"] = [
                f"High complexity: {s['name']} (cyclomatic={s['complexity']})"
                for s in high_complexity
            ]

    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="analyze_project",
          description="Analyze project structure: file counts by type, language breakdown, total LOC, dependencies.")
async def analyze_project(root_dir: str = ".", max_files: int = 200) -> str:
    root = Path(root_dir).expanduser().resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Directory not found: {root_dir}"}, ensure_ascii=False)

    files = _walk_files(str(root))[:max_files]
    by_lang: dict[str, list[Path]] = defaultdict(list)
    total_lines = 0
    total_code = 0

    for fp in files:
        lang = _detect_lang(fp)
        by_lang[lang].append(fp)
        text = _safe_read(fp)
        if text:
            lc = _count_lines(text)
            total_lines += lc["total"]
            total_code += lc["code"]

    lang_summary = {}
    for lang, lang_files in sorted(by_lang.items(), key=lambda x: -len(x[1])):
        lang_summary[lang] = {
            "count": len(lang_files),
            "files": [str(f.relative_to(root)) for f in lang_files[:20]],
        }

    all_imports = defaultdict(int)
    for fp in files:
        if fp.suffix == ".py":
            text = _safe_read(fp)
            if text:
                imps = _extract_imports(text)
                for imp in imps.get("third_party", []):
                    mod = imp.get("module", "")
                    if mod:
                        all_imports[mod] += 1

    top_deps = sorted(all_imports.items(), key=lambda x: -x[1])[:30]

    return json.dumps({
        "root": str(root),
        "total_files": len(files),
        "total_lines": total_lines,
        "total_code_lines": total_code,
        "languages": lang_summary,
        "top_dependencies": [{"name": n, "files": c} for n, c in top_deps],
    }, ensure_ascii=False)


@mcp.tool(name="complexity_report",
          description="Cyclomatic complexity report for all functions in a Python file.")
async def complexity_report(file_path: str, min_complexity: int = 1) -> str:
    path = Path(file_path).expanduser()
    if not path.is_file():
        return json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)

    text = _safe_read(path)
    if text is None:
        return json.dumps({"error": f"Cannot read file: {file_path}"}, ensure_ascii=False)

    structs = _parse_complexity(text)
    funcs = [s for s in structs if s.get("type") == "function" and s.get("complexity", 0) >= min_complexity]
    classes = [s for s in structs if s.get("type") == "class"]
    funcs.sort(key=lambda x: -x["complexity"])

    avg = sum(f["complexity"] for f in funcs) / len(funcs) if funcs else 0
    high = [f for f in funcs if f["complexity"] > 10]

    return json.dumps({
        "file": str(path),
        "total_functions": len(funcs),
        "total_classes": len(classes),
        "average_complexity": round(avg, 2),
        "max_complexity": max((f["complexity"] for f in funcs), default=0),
        "high_complexity_count": len(high),
        "functions": funcs,
        "classes": classes,
    }, ensure_ascii=False)


@mcp.tool(name="dependency_graph",
          description="Extract import dependency graph from a Python file or project directory.")
async def dependency_graph(target: str) -> str:
    path = Path(target).expanduser()
    if not path.exists():
        return json.dumps({"error": f"Target not found: {target}"}, ensure_ascii=False)

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    files = [path] if path.is_file() else _walk_files(str(path), exts={".py"})

    for fp in files:
        rel = str(fp.relative_to(path.parent) if path.is_file() else fp.relative_to(path))
        text = _safe_read(fp)
        if not text:
            continue

        nodes[rel] = {"file": rel, "language": "python", "imports": []}
        imps = _extract_imports(text)
        for imp in imps.get("third_party", []) + imps.get("imports", []) + imps.get("local", []):
            mod = imp.get("module", "")
            if mod:
                nodes[rel]["imports"].append(mod)
                edges.append({"from": rel, "to": mod, "type": imp.get("type", "unknown")})

    return json.dumps({
        "target": str(path),
        "files": len(files),
        "nodes": list(nodes.values()),
        "edges": edges,
    }, ensure_ascii=False)


@mcp.tool(name="security_scan",
          description="Scan source code for common security vulnerability patterns.")
async def security_scan(target: str) -> str:
    path = Path(target).expanduser()
    if not path.exists():
        return json.dumps({"error": f"Target not found: {target}"}, ensure_ascii=False)

    findings = []
    files = [path] if path.is_file() else _walk_files(str(path))

    for fp in files:
        text = _safe_read(fp)
        if not text:
            continue
        rel = str(fp.relative_to(path.parent) if path.is_file() else fp.relative_to(path))
        for fid, pattern, msg in _SECURITY_PATTERNS:
            for m in re.finditer(pattern, text):
                line_num = text[:m.start()].count("\n") + 1
                findings.append({
                    "file": rel,
                    "line": line_num,
                    "finding_id": fid,
                    "message": msg,
                    "match": m.group()[:80],
                })

    by_type: dict[str, int] = defaultdict(int)
    for f in findings:
        by_type[f["finding_id"]] += 1

    return json.dumps({
        "target": str(path),
        "files_scanned": len(files),
        "total_findings": len(findings),
        "by_type": dict(by_type),
        "findings": findings,
    }, ensure_ascii=False)


@mcp.tool(name="dead_code_finder",
          description="Find potentially unused code: unused imports, unreachable code in Python files.")
async def dead_code_finder(file_path: str) -> str:
    path = Path(file_path).expanduser()
    if not path.is_file():
        return json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)

    text = _safe_read(path)
    if text is None:
        return json.dumps({"error": f"Cannot read file: {file_path}"}, ensure_ascii=False)

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return json.dumps({"error": f"Syntax error: {e}"}, ensure_ascii=False)

    issues = []

    all_names: set[str] = set()
    defined_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_names.add(node.name)
            all_names.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Store))
        elif isinstance(node, ast.ClassDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined_names.add(t.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            unreachable = False
            for child in ast.walk(node):
                if isinstance(child, ast.Raise):
                    unreachable = True
            if unreachable:
                issues.append({
                    "type": "unreachable_code",
                    "name": node.name,
                    "line": node.lineno,
                    "detail": "Function contains bare raise — possible unreachable code after it",
                })

    unused_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in all_names:
                    unused_imports.append({
                        "name": alias.name,
                        "line": node.lineno,
                    })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name not in all_names and (alias.asname or alias.name) not in all_names:
                    unused_imports.append({
                        "name": f"{node.module}.{alias.name}" if node.module else alias.name,
                        "line": node.lineno,
                    })

    if unused_imports:
        issues.append({
            "type": "unused_import",
            "count": len(unused_imports),
            "imports": unused_imports,
        })

    return json.dumps({
        "file": str(path),
        "issues": issues,
        "summary": {
            "unused_imports": len(unused_imports),
            "unreachable_code": sum(1 for i in issues if i["type"] == "unreachable_code"),
        },
    }, ensure_ascii=False)


@mcp.tool(name="code_metrics",
          description="Calculate code metrics for a file or project: LOC, comment ratio, Halstead-like metrics.")
async def code_metrics(target: str) -> str:
    path = Path(target).expanduser()
    if not path.exists():
        return json.dumps({"error": f"Target not found: {target}"}, ensure_ascii=False)

    files = [path] if path.is_file() else _walk_files(str(path))
    metrics_list = []

    for fp in files:
        text = _safe_read(fp)
        if not text:
            continue
        rel = str(fp.relative_to(path.parent) if path.is_file() else fp.relative_to(path))
        lc = _count_lines(text)
        comment_ratio = round(lc["comment"] / lc["code"], 3) if lc["code"] else 0
        metrics_list.append({
            "file": rel,
            "language": _detect_lang(fp),
            "size_bytes": fp.stat().st_size,
            "total_lines": lc["total"],
            "code_lines": lc["code"],
            "blank_lines": lc["blank"],
            "comment_lines": lc["comment"],
            "comment_ratio": comment_ratio,
        })

    if not metrics_list:
        return json.dumps({"error": "No files found"}, ensure_ascii=False)

    totals = {
        "total_lines": sum(m["total_lines"] for m in metrics_list),
        "code_lines": sum(m["code_lines"] for m in metrics_list),
        "blank_lines": sum(m["blank_lines"] for m in metrics_list),
        "comment_lines": sum(m["comment_lines"] for m in metrics_list),
    }
    totals["comment_ratio"] = round(totals["comment_lines"] / totals["code_lines"], 3) if totals["code_lines"] else 0

    return json.dumps({
        "target": str(path),
        "files": len(metrics_list),
        "totals": totals,
        "per_file": metrics_list,
    }, ensure_ascii=False)


@mcp.tool(name="find_duplications",
          description="Find similar/duplicated code blocks in a file or across a project (simple line-hash approach).")
async def find_duplications(target: str, min_lines: int = 5, min_similarity: float = 0.9) -> str:
    path = Path(target).expanduser()
    if not path.exists():
        return json.dumps({"error": f"Target not found: {target}"}, ensure_ascii=False)

    files = [path] if path.is_file() else _walk_files(str(path))
    blocks: list[dict] = []

    for fp in files:
        text = _safe_read(fp)
        if not text:
            continue
        lines = text.splitlines()
        stripped = [l.strip() for l in lines]
        rel = str(fp.relative_to(path.parent) if path.is_file() else fp.relative_to(path))

        for i in range(len(lines) - min_lines + 1):
            block_hash = hash(tuple(stripped[i:i + min_lines]))
            blocks.append({
                "file": rel,
                "start_line": i + 1,
                "hash": block_hash,
                "text": "\n".join(lines[i:i + min_lines]),
            })

    hash_groups: dict[int, list[dict]] = defaultdict(list)
    for b in blocks:
        hash_groups[b["hash"]].append(b)

    dups = [v for v in hash_groups.values() if len(v) > 1]

    return json.dumps({
        "target": str(path),
        "total_blocks": len(blocks),
        "duplication_groups": len(dups),
        "duplications": [
            {
                "occurrences": [
                    {"file": d["file"], "line": d["start_line"]}
                    for d in group[:5]
                ],
                "lines": min_lines,
                "snippet": group[0]["text"][:200],
            }
            for group in dups[:20]
        ],
    }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
