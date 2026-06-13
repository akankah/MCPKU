"""
mcp_path_resolver.py — Path Resolution MCP Server
==================================================
Resolve relative/absolute paths, workspace roots, path normalization,
and cross-platform path handling for MCP filesystem operations.

References:
- MCP filesystem issues: https://github.com/modelcontextprotocol/servers/issues/2416
- Path resolution patterns from mcp_python_toolbox
"""

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("path-resolver", instructions="""
Path resolution utilities for MCP servers and AI agents.
Resolve relative paths to absolute, normalize cross-platform paths,
detect workspace roots, and validate path safety.

Tools:
- resolve_path: Relative -> absolute with workspace roots
- normalize_path: Cross-platform normalization (Windows/Unix)
- get_workspace_roots: Detect project roots (git, config files)
- is_path_allowed: Check against allowlist (security)
- path_to_url / url_to_path: File URI conversion
- get_path_info: Detailed path metadata
- join_paths: Safe path joining
- split_path: Split into components
""")


# ── Configuration ────────────────────────────────────────────────────────────

_FS_ALLOW_ALL = os.environ.get("MCP_FS_ALLOW_ALL", "0") == "1"
_EXTRA_ALLOWED = os.environ.get("MCP_EXTRA_ALLOWED_DIR", "").strip()
_BASE_DIR = Path(__file__).parent.resolve()

if os.name == "nt":
    _DEFAULT_ROOTS = [Path("C:/"), Path("D:/"), Path("E:/")]
else:
    _DEFAULT_ROOTS = [Path("/home"), Path("/tmp"), Path("/workspace")]

_ALLOWED_PREFIXES = tuple(
    str(p.resolve()) + os.sep
    for p in ([_BASE_DIR] + _DEFAULT_ROOTS + ([Path(_EXTRA_ALLOWED)] if _EXTRA_ALLOWED else []))
)

_WORKSPACE_MARKERS = {
    ".git", ".gitignore", "pyproject.toml", "setup.py", "requirements.txt",
    "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "mvnw", "gradlew", ".project", ".classpath", "composer.json",
    "Gemfile", "Makefile", "CMakeLists.txt", "meson.build"
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_with_roots(path: str, roots: List[Path]) -> Path:
    """Resolve path against workspace roots."""
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    for root in roots:
        candidate = (root / p).resolve()
        if candidate.exists() or candidate.parent.exists():
            return candidate
    return (_BASE_DIR / p).resolve()


def _find_workspace_roots(start: Path) -> List[Path]:
    """Walk up from start to find workspace root markers."""
    roots = []
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if any((parent / m).exists() for m in _WORKSPACE_MARKERS):
            roots.append(parent)
    return roots if roots else [current]


def _is_allowed(path: Path) -> bool:
    if _FS_ALLOW_ALL:
        return True
    resolved = str(path.resolve()) + os.sep
    return any(resolved.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _path_to_dict(p: Path) -> dict:
    return {
        "path": str(p),
        "absolute": str(p.resolve()),
        "is_absolute": p.is_absolute(),
        "exists": p.exists(),
        "is_file": p.is_file(),
        "is_dir": p.is_dir(),
        "is_symlink": p.is_symlink(),
        "size": p.stat().st_size if p.exists() else None,
        "modified": p.stat().st_mtime if p.exists() else None,
        "suffix": p.suffix,
        "stem": p.stem,
        "parent": str(p.parent),
        "name": p.name,
        "parts": list(p.parts),
        "allowed": _is_allowed(p),
    }


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(name="resolve_path",
          description="Resolve a path (relative or absolute) to absolute path using workspace roots.")
async def resolve_path(
    path: str,
    workspace_root: str = "",
    additional_roots: List[str] = None,
) -> str:
    roots = [Path(workspace_root).resolve()] if workspace_root else _find_workspace_roots(_BASE_DIR)
    if additional_roots:
        roots.extend([Path(r).resolve() for r in additional_roots])
    resolved = _resolve_with_roots(path, roots)
    return json.dumps({
        "input": path,
        "resolved": str(resolved),
        "workspace_roots_used": [str(r) for r in roots],
        "exists": resolved.exists(),
        "is_absolute": resolved.is_absolute(),
    }, ensure_ascii=False)


@mcp.tool(name="normalize_path",
          description="Normalize path for current platform (handle ~, ., .., symlinks, separators).")
async def normalize_path(path: str, expand_user: bool = True, resolve_symlinks: bool = True) -> str:
    p = Path(path)
    if expand_user:
        p = p.expanduser()
    if resolve_symlinks:
        try:
            p = p.resolve()
        except Exception:
            p = p.absolute()
    else:
        p = p.absolute()
    normalized = str(p).replace("\\", "/") if platform.system() == "Windows" else str(p)
    return json.dumps({
        "input": path,
        "normalized": normalized,
        "platform": platform.system(),
        "is_absolute": p.is_absolute(),
    }, ensure_ascii=False)


@mcp.tool(name="get_workspace_roots",
          description="Detect workspace/project roots from current directory or given path.")
async def get_workspace_roots(start_path: str = "") -> str:
    start = Path(start_path).resolve() if start_path else _BASE_DIR
    roots = _find_workspace_roots(start)
    markers_found = {}
    for root in roots:
        markers_found[str(root)] = [m for m in _WORKSPACE_MARKERS if (root / m).exists()]
    return json.dumps({
        "start_path": str(start),
        "roots": [str(r) for r in roots],
        "markers_found": markers_found,
    }, ensure_ascii=False)


@mcp.tool(name="is_path_allowed",
          description="Check if a path is within allowed directories (security check).")
async def is_path_allowed(path: str) -> str:
    p = Path(path).resolve()
    allowed = _is_allowed(p)
    return json.dumps({
        "path": str(p),
        "allowed": allowed,
        "allow_all_mode": _FS_ALLOW_ALL,
        "allowed_prefixes": list(_ALLOWED_PREFIXES) if not _FS_ALLOW_ALL else ["*"],
    }, ensure_ascii=False)


@mcp.tool(name="path_to_url",
          description="Convert local file path to file:// URI.")
async def path_to_url(path: str) -> str:
    p = Path(path).resolve()
    url = p.as_uri()
    return json.dumps({"path": str(p), "url": url}, ensure_ascii=False)


@mcp.tool(name="url_to_path",
          description="Convert file:// URI to local file path.")
async def url_to_path(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return json.dumps({"error": "Not a file:// URL"}, ensure_ascii=False)
    path = Path(parsed.path)
    if platform.system() == "Windows" and parsed.path.startswith("/"):
        path = Path(parsed.path[1:])
    return json.dumps({"url": url, "path": str(path.resolve())}, ensure_ascii=False)


@mcp.tool(name="get_path_info",
          description="Get detailed metadata for a path.")
async def get_path_info(path: str) -> str:
    p = Path(path)
    return json.dumps(_path_to_dict(p), ensure_ascii=False)


@mcp.tool(name="join_paths",
          description="Safely join multiple path components.")
async def join_paths(*parts: str) -> str:
    joined = Path(*parts).resolve()
    return json.dumps({
        "parts": list(parts),
        "joined": str(joined),
        "is_absolute": joined.is_absolute(),
    }, ensure_ascii=False)


@mcp.tool(name="split_path",
          description="Split path into components (drive, root, directories, file).")
async def split_path(path: str) -> str:
    p = Path(path)
    return json.dumps({
        "path": str(p),
        "drive": p.drive,
        "root": p.root,
        "anchor": p.anchor,
        "parent": str(p.parent),
        "name": p.name,
        "stem": p.stem,
        "suffix": p.suffix,
        "suffixes": p.suffixes,
        "parts": list(p.parts),
    }, ensure_ascii=False)


@mcp.tool(name="relative_to",
          description="Compute relative path from base to target.")
async def relative_to(target: str, base: str = "") -> str:
    target_p = Path(target).resolve()
    base_p = Path(base).resolve() if base else _BASE_DIR
    try:
        rel = target_p.relative_to(base_p)
        return json.dumps({
            "target": str(target_p),
            "base": str(base_p),
            "relative": str(rel),
            "success": True,
        }, ensure_ascii=False)
    except ValueError:
        return json.dumps({
            "target": str(target_p),
            "base": str(base_p),
            "relative": None,
            "success": False,
            "error": "Target not under base",
        }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
