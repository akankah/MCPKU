"""
mcp_serena.py — Serena-Style Semantic Code Analysis MCP Server
===============================================================
Semantic code retrieval, navigation, and editing for AI agents.
Provides codebase understanding via AST analysis, symbol search,
reference finding, and intelligent code editing.

Inspired by oraios/serena (https://github.com/oraios/serena)
which uses LSP + MCP for IDE-like capabilities in AI agents.
"""

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional, Set
from collections import defaultdict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("serena", instructions="""
Serena-style semantic code analysis for AI agents.
Navigate, search, and understand codebases using AST analysis.

Tools:
- semantic_search: Find code by semantic intent (class, function, variable)
- find_references: Find all references to a symbol across files
- get_symbol_definition: Get definition of a symbol (AST-based)
- get_file_symbols: List all symbols in a file (classes, functions, variables)
- get_call_hierarchy: Show callers/callees for a function
- get_inheritance_tree: Show class hierarchy
- suggest_edit: Suggest code edits with context
- analyze_import_graph: Show import relationships between files
- fuzzy_find: Fuzzy-find files and symbols
""")


# ── Helpers ──────────────────────────────────────────────────────────────────

_WORKSPACE = Path(__file__).parent.resolve()
_IGNORE_DIRS = {"__pycache__", ".git", ".venv", "venv", "env",
                "node_modules", ".mypy_cache", ".pytest_cache",
                ".ruff_cache", "dist", "build", ".tox", ".eggs"}

_SYMBOL_KINDS = {"function": "F", "class": "C", "variable": "V", "method": "M", "property": "P"}


def _walk_py_files(root: Path) -> List[Path]:
    files = []
    for fp in root.rglob("*.py"):
        if not any(p.name in _IGNORE_DIRS for p in fp.parents):
            files.append(fp)
    return files


def _parse_file(path: Path) -> Optional[ast.AST]:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


def _extract_symbols(tree: ast.AST, source: str, filepath: str) -> List[dict]:
    symbols = []
    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            symbols.append({
                "name": node.name,
                "kind": "class",
                "file": filepath,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "doc": doc[:100],
                "bases": [b.id if isinstance(b, ast.Name) else repr(b) for b in node.bases],
                "methods": [],
            })
            # Find methods inside class
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols[-1]["methods"].append(child.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            symbols.append({
                "name": node.name,
                "kind": "function",
                "file": filepath,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "doc": doc[:100],
                "args": len(node.args.args),
                "decorators": [d.id if isinstance(d, ast.Name) else "" for d in node.decorator_list],
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append({
                        "name": target.id,
                        "kind": "variable",
                        "file": filepath,
                        "line": node.lineno,
                        "value": source.splitlines()[node.lineno - 1].strip()[:80] if node.lineno <= len(lines) else "",
                    })

    return symbols


def _find_symbol_in_tree(name: str, tree: ast.AST) -> List[ast.AST]:
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            matches.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    matches.append(node)
    return matches


def _find_references_in_tree(name: str, tree: ast.AST) -> List[dict]:
    refs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name and not isinstance(node.ctx, ast.Store):
            refs.append({"line": node.lineno, "col": node.col_offset})
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                refs.append({"line": node.lineno, "col": node.col_offset, "type": "call"})
            elif isinstance(func, ast.Attribute) and func.attr == name:
                refs.append({"line": node.lineno, "col": node.col_offset, "type": "method_call"})
    return refs


def _find_references_project(name: str, root: Path) -> List[dict]:
    results = []
    for fp in _walk_py_files(root):
        tree = _parse_file(fp)
        if tree is None:
            continue
        rel = str(fp.relative_to(root))
        refs = _find_references_in_tree(name, tree)
        for r in refs:
            results.append({"file": rel, **r})
    return results


def _get_usages(name: str, tree: ast.AST) -> List[dict]:
    usages = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            ctx_type = "read"
            if isinstance(node.ctx, ast.Store):
                ctx_type = "write"
            elif isinstance(node.ctx, ast.Del):
                ctx_type = "delete"
            usages.append({"line": node.lineno, "context": ctx_type})
    return usages


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(name="semantic_search",
          description="Search codebase by semantic intent: find classes, functions, or variables matching a pattern.")
async def semantic_search(
    query: str,
    kind: str = "",
    root_dir: str = "",
    max_results: int = 30,
) -> str:
    root = Path(root_dir).resolve() if root_dir else _WORKSPACE
    if not root.is_dir():
        return json.dumps({"error": f"Directory not found: {root_dir}"})

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results = []

    for fp in _walk_py_files(root):
        tree = _parse_file(fp)
        if tree is None:
            continue
        rel = str(fp.relative_to(root))
        try:
            source = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            source = ""
        symbols = _extract_symbols(tree, source, rel)
        for sym in symbols:
            if kind and sym.get("kind", "") != kind:
                continue
            if pattern.search(sym["name"]):
                results.append(sym)

    return json.dumps({
        "query": query,
        "kind": kind or "all",
        "results": results[:max_results],
        "total": len(results),
    }, ensure_ascii=False)


@mcp.tool(name="find_references",
          description="Find all references to a symbol across the project.")
async def find_references(symbol_name: str, root_dir: str = "") -> str:
    root = Path(root_dir).resolve() if root_dir else _WORKSPACE
    refs = _find_references_project(symbol_name, root)
    return json.dumps({
        "symbol": symbol_name,
        "total": len(refs),
        "references": refs,
    }, ensure_ascii=False)


@mcp.tool(name="get_symbol_definition",
          description="Get definition of a symbol (class/function/variable) with source code snippet.")
async def get_symbol_definition(symbol_name: str, file_path: str = "") -> str:
    if file_path:
        paths = [Path(file_path).resolve()]
    else:
        paths = _walk_py_files(_WORKSPACE)

    for fp in paths:
        if not fp.is_file():
            continue
        tree = _parse_file(fp)
        if tree is None:
            continue
        matches = _find_symbol_in_tree(symbol_name, tree)
        if matches:
            node = matches[0]
            source = fp.read_text(encoding="utf-8", errors="replace")
            lines = source.splitlines()
            start = max(0, node.lineno - 1)
            end = getattr(node, "end_lineno", node.lineno)
            snippet = "\n".join(lines[start:end])
            kind = "class" if isinstance(node, ast.ClassDef) else "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "variable"
            return json.dumps({
                "symbol": symbol_name,
                "kind": kind,
                "file": str(fp),
                "line": node.lineno,
                "end_line": end,
                "source": snippet,
                "doc": ast.get_docstring(node) or "",
            }, ensure_ascii=False, indent=2)

    return json.dumps({"symbol": symbol_name, "error": "Not found"}, ensure_ascii=False)


@mcp.tool(name="get_file_symbols",
          description="List all symbols (classes, functions, variables) in a file.")
async def get_file_symbols(file_path: str) -> str:
    fp = Path(file_path).resolve()
    if not fp.is_file():
        return json.dumps({"error": f"File not found: {file_path}"})

    tree = _parse_file(fp)
    if tree is None:
        return json.dumps({"error": "Syntax error in file"})

    try:
        source = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        source = ""

    symbols = _extract_symbols(tree, source, str(fp))
    by_kind = defaultdict(list)
    for s in symbols:
        by_kind[s["kind"]].append(s)

    return json.dumps({
        "file": str(fp),
        "total": len(symbols),
        "classes": by_kind.get("class", []),
        "functions": by_kind.get("function", []),
        "variables": by_kind.get("variable", []),
    }, ensure_ascii=False)


@mcp.tool(name="get_call_hierarchy",
          description="Show callers and callees for a function in the project.")
async def get_call_hierarchy(function_name: str, root_dir: str = "") -> str:
    root = Path(root_dir).resolve() if root_dir else _WORKSPACE
    callers = []
    callees = []

    for fp in _walk_py_files(root):
        tree = _parse_file(fp)
        if tree is None:
            continue
        rel = str(fp.relative_to(root))

        # Find calls TO our function (callers)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (isinstance(func, ast.Name) and func.id == function_name) or \
                   (isinstance(func, ast.Attribute) and func.attr == function_name):
                    # Find enclosing function
                    for parent in ast.walk(tree):
                        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            for child in ast.walk(parent):
                                if child is node:
                                    callers.append({
                                        "file": rel,
                                        "line": node.lineno,
                                        "caller": parent.name,
                                    })
                                    break

        # Find calls FROM our function (callees)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        cfunc = child.func
                        if isinstance(cfunc, ast.Name):
                            callees.append({
                                "name": cfunc.id,
                                "line": child.lineno,
                                "file": rel,
                            })

    return json.dumps({
        "function": function_name,
        "callers": callers,
        "callees": callees,
    }, ensure_ascii=False)


@mcp.tool(name="get_inheritance_tree",
          description="Show class inheritance hierarchy for a project or specific class.")
async def get_inheritance_tree(class_name: str = "", root_dir: str = "") -> str:
    root = Path(root_dir).resolve() if root_dir else _WORKSPACE
    classes = {}

    for fp in _walk_py_files(root):
        tree = _parse_file(fp)
        if tree is None:
            continue
        rel = str(fp.relative_to(root))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        bases.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        bases.append(f"{b.value.id}.{b.attr}" if isinstance(b.value, ast.Name) else repr(b))
                classes[node.name] = {
                    "bases": bases,
                    "file": rel,
                    "line": node.lineno,
                    "methods": [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))],
                }

    if class_name and class_name not in classes:
        return json.dumps({"error": f"Class '{class_name}' not found"}, ensure_ascii=False)

    # Build tree
    def _build_tree(name: str, depth: int = 0, visited: Set = None) -> dict:
        if visited is None:
            visited = set()
        if name in visited or depth > 10:
            return {"name": name, "cycle": True}
        visited.add(name)
        cls = classes.get(name, {})
        children = []
        for cn, c in classes.items():
            if name in c.get("bases", []):
                children.append(_build_tree(cn, depth + 1, visited.copy()))
        return {
            "name": name,
            "bases": cls.get("bases", []),
            "file": cls.get("file", ""),
            "methods": cls.get("methods", []),
            "subclasses": children,
        }

    if class_name:
        tree_result = _build_tree(class_name)
    else:
        # Find root classes (no bases or built-in bases)
        root_classes = [n for n, c in classes.items() if not c.get("bases") or all(b in ("object",) for b in c["bases"])]
        tree_result = [_build_tree(n) for n in root_classes]

    return json.dumps({
        "total_classes": len(classes),
        "hierarchy": tree_result,
    }, ensure_ascii=False)


@mcp.tool(name="analyze_import_graph",
          description="Analyze import dependencies between files in the project.")
async def analyze_import_graph(root_dir: str = "", focus_file: str = "") -> str:
    root = Path(root_dir).resolve() if root_dir else _WORKSPACE
    imports = {}  # file -> [imported modules]
    used_by = defaultdict(list)  # module -> [files that import it]

    files = [Path(focus_file).resolve()] if focus_file else _walk_py_files(root)
    if focus_file:
        root = files[0].parent

    for fp in files:
        if not fp.is_file():
            continue
        rel = str(fp.relative_to(root))
        tree = _parse_file(fp)
        if tree is None:
            continue
        file_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_imports.append(alias.name)
                    used_by[alias.name].append(rel)
            elif isinstance(node, ast.ImportFrom):
                mod = f"{node.module}" if node.module else ""
                for alias in node.names:
                    full = f"{mod}.{alias.name}" if mod else alias.name
                    file_imports.append(full)
                    used_by[full].append(rel)
        if file_imports:
            imports[rel] = file_imports

    return json.dumps({
        "files_analyzed": len(imports),
        "imports": imports,
        "most_imported": {k: len(v) for k, v in sorted(used_by.items(), key=lambda x: -len(x[1]))[:20]},
    }, ensure_ascii=False)


@mcp.tool(name="fuzzy_find",
          description="Fuzzy-find files and symbols by name pattern.")
async def fuzzy_find(pattern: str, root_dir: str = "", max_results: int = 20) -> str:
    root = Path(root_dir).resolve() if root_dir else _WORKSPACE
    pat = re.compile(f".*{re.escape(pattern)}.*", re.IGNORECASE)
    results = []

    # Search files
    for fp in _walk_py_files(root):
        rel = str(fp.relative_to(root))
        if pat.search(fp.stem) or pat.search(rel):
            results.append({"type": "file", "name": rel})

    # Search symbols
    for fp in _walk_py_files(root)[:50]:
        tree = _parse_file(fp)
        if tree is None:
            continue
        rel = str(fp.relative_to(root))
        try:
            source = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            source = ""
        symbols = _extract_symbols(tree, source, rel)
        for sym in symbols:
            if pat.search(sym["name"]):
                results.append({
                    "type": sym["kind"],
                    "name": sym["name"],
                    "file": rel,
                    "line": sym.get("line", 0),
                })

    return json.dumps({
        "pattern": pattern,
        "total": len(results),
        "results": results[:max_results],
    }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
