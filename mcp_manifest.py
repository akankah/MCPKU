"""
mcp_manifest.py — Central tool metadata for MCPKU.

Single source of truth for all MCPKU tools: their module, category,
parameter signatures, danger level, and execution policy hints.

Usage:
    from mcp_manifest import TOOL_MANIFEST, get_tool, register_all, ToolEntry
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolEntry:
    name: str
    module: str
    func_name: str
    category: str = "general"
    description: str = ""
    dangerous: bool = False
    requires_repo: bool = False
    requires_network: bool = False
    timeout_suggestion: int = 30
    parallel_ok: bool = False

    _func: Callable | None = field(default=None, repr=False)

    def get_func(self) -> Callable:
        if self._func is None:
            mod = importlib.import_module(self.module)
            self._func = getattr(mod, self.func_name)
        return self._func

    def get_params(self) -> list[dict]:
        func = self.get_func()
        sig = inspect.signature(func)
        params = []
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            entry = {"name": pname, "kind": param.kind.name}
            if param.annotation is not inspect.Parameter.empty:
                ann = param.annotation
                if hasattr(ann, "__name__"):
                    entry["type"] = ann.__name__
                else:
                    entry["type"] = str(ann)
            if param.default is not inspect.Parameter.empty:
                entry["default"] = param.default
            params.append(entry)
        return params


def _entry(name: str, module: str, func: str, **kw) -> tuple[str, ToolEntry]:
    return name, ToolEntry(name=name, module=module, func_name=func, **kw)


TOOL_MANIFEST: dict[str, ToolEntry] = dict([

    # ── Research (mcp_web + mcp_research) ──
    _entry("auto_research", "agentku_buat_chat", "_auto_research",
           category="research", description="Smart search DDG+Firecrawl+auto-fetch", requires_network=True, timeout_suggestion=20, parallel_ok=True),
    _entry("web_search_web", "mcp_web", "search_web",
           category="research", description="Web search via DuckDuckGo", requires_network=True, timeout_suggestion=15, parallel_ok=True),
    _entry("web_search_stackoverflow", "mcp_web", "search_stackoverflow",
           category="research", description="Search Stack Overflow", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("web_fetch_url", "mcp_web", "fetch_url",
           category="research", description="Fetch URL content", requires_network=True, timeout_suggestion=15, parallel_ok=True),
    _entry("get_stack_content", "mcp_web", "get_stack_content",
           category="research", description="Get Stack Exchange question+answers", requires_network=True, timeout_suggestion=10),
    _entry("search_npm", "mcp_web", "search_npm",
           category="research", description="Search npm packages", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("search_pypi", "mcp_web", "search_pypi",
           category="research", description="Search PyPI packages", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("search_crates", "mcp_web", "search_crates",
           category="research", description="Search Rust crates", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("search_readthedocs", "mcp_web", "search_readthedocs",
           category="research", description="Search ReadTheDocs", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("search_mdn", "mcp_web", "search_mdn",
           category="research", description="Search MDN web docs", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("search_devdocs", "mcp_web", "search_devdocs",
           category="research", description="Search DevDocs API docs", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("research_query", "mcp_research", "query",
           category="research", description="Full multi-source research query", requires_network=True, timeout_suggestion=20),
    _entry("research_quick", "mcp_research", "quick",
           category="research", description="Fast 2-source check", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("research_deep", "mcp_research", "deep",
           category="research", description="Deep 8-source cross-validation", requires_network=True, timeout_suggestion=30),
    _entry("browser_fetch", "mcp_browser", "browser_fetch",
           category="research", description="Headless browser fetch for JS sites", requires_network=True, timeout_suggestion=30),
    _entry("screenshot", "mcp_browser", "screenshot",
           category="research", description="Take browser screenshot", requires_network=True, timeout_suggestion=30),

    # ── Memory ──
    _entry("memory_search_nodes", "mcp_memory", "search_nodes",
           category="memory", description="Search knowledge graph nodes"),
    _entry("memory_create_entities", "mcp_memory", "create_entities",
           category="memory", description="Create entities in knowledge graph"),
    _entry("memory_add_observations", "mcp_memory", "add_observations",
           category="memory", description="Add observations to existing entities"),
    _entry("memory_delete_entities", "mcp_memory", "delete_entities",
           category="memory", description="Delete entities from knowledge graph", dangerous=True),
    _entry("memory_open_nodes", "mcp_memory", "open_nodes",
           category="memory", description="Open specific nodes by name"),
    _entry("memory_read_graph", "mcp_memory", "read_graph",
           category="memory", description="Read entire knowledge graph"),
    _entry("memory_create_relations", "mcp_memory", "create_relations",
           category="memory", description="Create relations between entities"),
    _entry("memory_delete_observations", "mcp_memory", "delete_observations",
           category="memory", description="Delete observations from entities", dangerous=True),
    _entry("memory_delete_relations", "mcp_memory", "delete_relations",
           category="memory", description="Delete relations from graph", dangerous=True),

    # ── Debug / Diagnostics ──
    _entry("autofix_run", "mcp_autofix", "autofix_run",
           category="debug", description="Run command with auto-fix", dangerous=True, timeout_suggestion=120),
    _entry("autofix_search_kb", "mcp_autofix", "autofix_search_kb",
           category="debug", description="Search error knowledge base"),
    _entry("autofix_save_error", "mcp_autofix", "autofix_save_error",
           category="debug", description="Save error to knowledge base"),
    _entry("autofix_history", "mcp_autofix", "autofix_history",
           category="debug", description="Show auto-fix session history"),
    _entry("autofix_strategies", "mcp_autofix", "autofix_strategies",
           category="debug", description="List all auto-fix strategies"),
    _entry("autofix_kb_stats", "mcp_autofix", "autofix_kb_stats",
           category="debug", description="Knowledge base statistics"),
    _entry("autofix_kb_trends", "mcp_autofix", "autofix_kb_trends",
           category="debug", description="Multi-session error trends"),
    _entry("diagnostics_parse_traceback", "mcp_diagnostics", "parse_traceback",
           category="debug", description="Parse traceback into structured info"),
    _entry("diagnostics_classify_error", "mcp_diagnostics", "classify_error",
           category="debug", description="Classify error type"),
    _entry("diagnostics_explain_error", "mcp_diagnostics", "explain_error",
           category="debug", description="In-depth error explanation"),
    _entry("diagnostics_read_log_tail", "mcp_diagnostics", "read_log_tail",
           category="debug", description="Read last N log lines"),
    _entry("diagnostics_scan_project_errors", "mcp_diagnostics", "scan_project_errors",
           category="debug", description="Scan folder for error files"),
    _entry("diagnostics_watch_stderr", "mcp_diagnostics", "watch_stderr",
           category="debug", description="Run command and parse stderr"),
    _entry("diagnostics_get_error_history", "mcp_diagnostics", "get_error_history",
           category="debug", description="Show error history for session"),

    # ── Filesystem ──
    _entry("fs_read_file", "mcp_filesystem", "read_file",
           category="files", description="Read file contents"),
    _entry("fs_read_multiple_files", "mcp_filesystem", "read_multiple_files",
           category="files", description="Read multiple files at once"),
    _entry("fs_write_file", "mcp_filesystem", "write_file",
           category="files", description="Write/overwrite file", dangerous=True),
    _entry("fs_append_file", "mcp_filesystem", "append_file",
           category="files", description="Append to file", dangerous=True),
    _entry("fs_edit_file", "mcp_filesystem", "edit_file",
           category="files", description="Edit file with pattern matching", dangerous=True),
    _entry("fs_create_directory", "mcp_filesystem", "create_directory",
           category="files", description="Create directory"),
    _entry("fs_list_directory", "mcp_filesystem", "list_directory",
           category="files", description="List directory contents"),
    _entry("fs_list_directory_detailed", "mcp_filesystem", "list_directory_detailed",
           category="files", description="List directory with details"),
    _entry("fs_directory_tree", "mcp_filesystem", "directory_tree",
           category="files", description="Recursive directory tree"),
    _entry("fs_copy_file", "mcp_filesystem", "copy_file",
           category="files", description="Copy file/directory"),
    _entry("fs_move_file", "mcp_filesystem", "move_file",
           category="files", description="Move/rename file", dangerous=True),
    _entry("fs_delete_file", "mcp_filesystem", "delete_file",
           category="files", description="Delete file/directory", dangerous=True),
    _entry("fs_search_files", "mcp_filesystem", "search_files",
           category="files", description="Search files by glob pattern"),
    _entry("fs_grep_files", "mcp_filesystem", "grep_files",
           category="files", description="Search file contents by regex"),
    _entry("fs_glob_pattern", "mcp_filesystem", "glob_pattern",
           category="files", description="Match paths by glob"),
    _entry("fs_get_file_info", "mcp_filesystem", "get_file_info",
           category="files", description="Get file metadata"),
    _entry("fs_path_exists", "mcp_filesystem", "path_exists",
           category="files", description="Check if path exists"),
    _entry("fs_list_allowed_directories", "mcp_filesystem", "list_allowed_directories",
           category="files", description="List allowed access directories"),
    _entry("fs_diff_files", "mcp_filesystem", "diff_files",
           category="files", description="Show diff between files"),

    # ── Git ──
    _entry("git_status", "mcp_git", "git_status",
           category="git", description="Check git status", requires_repo=True),
    _entry("git_log", "mcp_git", "git_log",
           category="git", description="Show commit log", requires_repo=True),
    _entry("git_commit", "mcp_git", "git_commit",
           category="git", description="Commit changes", requires_repo=True, dangerous=True),

    # ── Think ──
    _entry("think", "mcp_think", "think",
           category="think", description="Record a reasoning step"),

    # ── Bash ──
    _entry("bash_run_command", "mcp_bash", "run_command",
           category="bash", description="Run shell command", dangerous=True, timeout_suggestion=60),

    # ── Planner ──
    _entry("planner_plan_generate", "mcp_planner", "plan_generate",
           category="plan", description="Generate reusable workflow plan"),
])

# ── Category groupings ──
CATEGORY_TOOLS: dict[str, list[str]] = {}
for _name, _entry in TOOL_MANIFEST.items():
    CATEGORY_TOOLS.setdefault(_entry.category, []).append(_name)


def get_tool(name: str) -> ToolEntry | None:
    return TOOL_MANIFEST.get(name)


def get_tools_by_category(category: str) -> list[ToolEntry]:
    return [TOOL_MANIFEST[n] for n in CATEGORY_TOOLS.get(category, [])]


def get_categories() -> list[str]:
    return list(CATEGORY_TOOLS.keys())


def register_all(registry: dict[str, Any]):
    for name, entry in TOOL_MANIFEST.items():
        try:
            registry[name] = entry.get_func()
        except Exception:
            pass
