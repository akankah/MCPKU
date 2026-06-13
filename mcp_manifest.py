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
           category="research", description="Full multi-source research query", requires_network=True, timeout_suggestion=15, parallel_ok=True),
    _entry("research_quick", "mcp_research", "quick",
           category="research", description="Fast 2-source check", requires_network=True, timeout_suggestion=8, parallel_ok=True),
    _entry("research_deep", "mcp_research", "deep",
           category="research", description="Deep 8-source cross-validation", requires_network=True, timeout_suggestion=25, parallel_ok=True),
    _entry("browser_fetch", "mcp_browser", "browser_fetch",
           category="research", description="Headless browser fetch for JS sites", requires_network=True, timeout_suggestion=20),
    _entry("screenshot", "mcp_browser", "screenshot",
           category="research", description="Take browser screenshot", requires_network=True, timeout_suggestion=15),

    # ── Memory ──
    _entry("memory_search_nodes", "mcp_memory", "search_nodes",
           category="memory", description="Search knowledge graph nodes", parallel_ok=True),
    _entry("memory_create_entities", "mcp_memory", "create_entities",
           category="memory", description="Create entities in knowledge graph"),
    _entry("memory_add_observations", "mcp_memory", "add_observations",
           category="memory", description="Add observations to existing entities"),
    _entry("memory_delete_entities", "mcp_memory", "delete_entities",
           category="memory", description="Delete entities from knowledge graph", dangerous=True),
    _entry("memory_open_nodes", "mcp_memory", "open_nodes",
           category="memory", description="Open specific nodes by name", parallel_ok=True),
    _entry("memory_read_graph", "mcp_memory", "read_graph",
           category="memory", description="Read entire knowledge graph", parallel_ok=True),
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
           category="debug", description="Search error knowledge base", parallel_ok=True),
    _entry("autofix_save_error", "mcp_autofix", "autofix_save_error",
           category="debug", description="Save error to knowledge base"),
    _entry("autofix_history", "mcp_autofix", "autofix_history",
           category="debug", description="Show auto-fix session history", parallel_ok=True),
    _entry("autofix_strategies", "mcp_autofix", "autofix_strategies",
           category="debug", description="List all auto-fix strategies", parallel_ok=True),
    _entry("autofix_kb_stats", "mcp_autofix", "autofix_kb_stats",
           category="debug", description="Knowledge base statistics", parallel_ok=True),
    _entry("autofix_kb_trends", "mcp_autofix", "autofix_kb_trends",
           category="debug", description="Multi-session error trends", parallel_ok=True),
    _entry("diagnostics_parse_traceback", "mcp_diagnostics", "parse_traceback",
           category="debug", description="Parse traceback into structured info"),
    _entry("diagnostics_classify_error", "mcp_diagnostics", "classify_error",
           category="debug", description="Classify error type", parallel_ok=True),
    _entry("diagnostics_explain_error", "mcp_diagnostics", "explain_error",
           category="debug", description="In-depth error explanation", parallel_ok=True),
    _entry("diagnostics_read_log_tail", "mcp_diagnostics", "read_log_tail",
           category="debug", description="Read last N log lines"),
    _entry("diagnostics_scan_project_errors", "mcp_diagnostics", "scan_project_errors",
           category="debug", description="Scan folder for error files"),
    _entry("diagnostics_watch_stderr", "mcp_diagnostics", "watch_stderr",
           category="debug", description="Run command and parse stderr"),
    _entry("diagnostics_get_error_history", "mcp_diagnostics", "get_error_history",
           category="debug", description="Show error history for session", parallel_ok=True),

    # ── Filesystem ──
    _entry("fs_read_file", "mcp_filesystem", "read_file",
           category="files", description="Read file contents", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_read_multiple_files", "mcp_filesystem", "read_multiple_files",
           category="files", description="Read multiple files at once", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_write_file", "mcp_filesystem", "write_file",
           category="files", description="Write/overwrite file", dangerous=True),
    _entry("fs_append_file", "mcp_filesystem", "append_file",
           category="files", description="Append to file", dangerous=True),
    _entry("fs_edit_file", "mcp_filesystem", "edit_file",
           category="files", description="Edit file with pattern matching", dangerous=True),
    _entry("fs_create_directory", "mcp_filesystem", "create_directory",
           category="files", description="Create directory", parallel_ok=True),
    _entry("fs_list_directory", "mcp_filesystem", "list_directory",
           category="files", description="List directory contents", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_list_directory_detailed", "mcp_filesystem", "list_directory_detailed",
           category="files", description="List directory with details", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_directory_tree", "mcp_filesystem", "directory_tree",
           category="files", description="Recursive directory tree", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_copy_file", "mcp_filesystem", "copy_file",
           category="files", description="Copy file/directory", parallel_ok=True),
    _entry("fs_move_file", "mcp_filesystem", "move_file",
           category="files", description="Move/rename file", dangerous=True),
    _entry("fs_delete_file", "mcp_filesystem", "delete_file",
           category="files", description="Delete file/directory", dangerous=True),
    _entry("fs_search_files", "mcp_filesystem", "search_files",
           category="files", description="Search files by glob pattern", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_grep_files", "mcp_filesystem", "grep_files",
           category="files", description="Search file contents by regex", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_glob_pattern", "mcp_filesystem", "glob_pattern",
           category="files", description="Match paths by glob", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_get_file_info", "mcp_filesystem", "get_file_info",
           category="files", description="Get file metadata", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_path_exists", "mcp_filesystem", "path_exists",
           category="files", description="Check if path exists", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_list_allowed_directories", "mcp_filesystem", "list_allowed_directories",
           category="files", description="List allowed access directories", parallel_ok=True, timeout_suggestion=10),
    _entry("fs_diff_files", "mcp_filesystem", "diff_files",
           category="files", description="Show diff between files", parallel_ok=True, timeout_suggestion=10),

    # ── Git ──
    _entry("git_status", "mcp_git", "git_status",
           category="git", description="Check git status", requires_repo=True, parallel_ok=True),
    _entry("git_log", "mcp_git", "git_log",
           category="git", description="Show commit log", requires_repo=True, parallel_ok=True),
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

    # ── Agent ──
    _entry("agent_plan", "agentku_buat_chat", "agent_plan",
           category="plan", description="Create DAG plan from goal"),
    _entry("agent_execute", "agentku_buat_chat", "agent_execute",
           category="plan", description="Execute a plan step"),
    _entry("agent_execute_all", "agentku_buat_chat", "agent_execute_all",
           category="plan", description="Execute all pending plan steps"),
    _entry("agent_list_plans", "agentku_buat_chat", "agent_list_plans",
           category="plan", description="List all saved plans"),
    _entry("agent_status", "agentku_buat_chat", "agent_status",
           category="plan", description="Check plan execution status"),
    _entry("agent_mark_step", "agentku_buat_chat", "agent_mark_step",
           category="plan", description="Mark plan step completed/failed"),

    # ── Time ──
    _entry("time_get_current_time", "mcp_time", "get_current_time",
           category="time", description="Get current time in timezone", parallel_ok=True),
    _entry("time_convert_time", "mcp_time", "convert_time",
           category="time", description="Convert time between timezones", parallel_ok=True),
    _entry("time_list_timezones", "mcp_time", "list_timezones",
           category="time", description="List available IANA timezones", parallel_ok=True),

    # ── GitHub ──
    _entry("github_get_repo", "mcp_github", "get_repo",
           category="github", description="Get repository details", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("github_list_issues", "mcp_github", "list_issues",
           category="github", description="List issues", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("github_create_issue", "mcp_github", "create_issue",
           category="github", description="Create issue", requires_network=True, dangerous=True, timeout_suggestion=15),
    _entry("github_list_pull_requests", "mcp_github", "list_pull_requests",
           category="github", description="List pull requests", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("github_create_pull_request", "mcp_github", "create_pull_request",
           category="github", description="Create pull request", requires_network=True, dangerous=True, timeout_suggestion=15),
    _entry("github_search_code", "mcp_github", "search_code",
           category="github", description="Search code in repo", requires_network=True, timeout_suggestion=15, parallel_ok=True),
    _entry("github_search_issues", "mcp_github", "search_issues",
           category="github", description="Search issues/PRs", requires_network=True, timeout_suggestion=15, parallel_ok=True),
    _entry("github_get_file_contents", "mcp_github", "get_file_contents",
           category="github", description="Get file contents from repo", requires_network=True, timeout_suggestion=8, parallel_ok=True),
    _entry("github_list_workflows", "mcp_github", "list_workflows",
           category="github", description="List GitHub Actions workflows", requires_network=True, timeout_suggestion=10, parallel_ok=True),
    _entry("github_trigger_workflow", "mcp_github", "trigger_workflow",
           category="github", description="Trigger workflow run", requires_network=True, dangerous=True, timeout_suggestion=30),

    # ── Vector ──
    _entry("vector_create_collection", "mcp_vector", "create_collection",
           category="vector", description="Create vector collection"),
    _entry("vector_add_documents", "mcp_vector", "add_documents",
           category="vector", description="Add documents to vector collection"),
    _entry("vector_search", "mcp_vector", "search",
           category="vector", description="Semantic search in vector collection", parallel_ok=True),
    _entry("vector_collection_stats", "mcp_vector", "collection_stats",
           category="vector", description="Get collection statistics", parallel_ok=True),
    _entry("vector_delete_documents", "mcp_vector", "delete_documents",
           category="vector", description="Delete documents from collection", dangerous=True),
    _entry("vector_list_collections", "mcp_vector", "list_collections",
           category="vector", description="List all vector collections", parallel_ok=True),

    # ── Git Doc ──
    _entry("git_doc_generate_commit_proposal", "mcp_git_doc", "generate_commit_proposal",
           category="git", description="Generate commit message from staged changes", requires_repo=True, parallel_ok=True),
    _entry("git_doc_generate_pr_summary", "mcp_git_doc", "generate_pr_summary",
           category="git", description="Generate PR summary from diff", requires_repo=True, parallel_ok=True),

    # ── API Tester ──
    _entry("api_tester_performance_test", "mcp_api_tester", "performance_test",
           category="perf", description="Test endpoint latency over multiple requests", requires_network=True, timeout_suggestion=60),
    _entry("api_tester_stress_test", "mcp_api_tester", "stress_test",
           category="perf", description="High concurrency stress test", requires_network=True, timeout_suggestion=120),

    # ── Perf Fixer ──
    _entry("perf_fixer_analyze_performance_report", "mcp_perf_fixer", "analyze_performance_report",
           category="perf", description="Analyze API tester report for optimization", parallel_ok=True),
    _entry("perf_fixer_bridge_to_autofix", "mcp_perf_fixer", "bridge_to_autofix",
           category="perf", description="Trigger autofix from high latency"),

    # ── Refactor ──
    _entry("refactor_check_code_smells", "mcp_refactor", "check_code_smells",
           category="refactor", description="Scan for long functions, deep nesting", parallel_ok=True),
    _entry("refactor_clean_python_code", "mcp_refactor", "clean_python_code",
           category="refactor", description="Remove unused imports, format with black", dangerous=True),
    _entry("refactor_rename_symbol_project", "mcp_refactor", "rename_symbol_project",
           category="refactor", description="Rename symbol across project", dangerous=True),

    # ── Doc Intel ──
    _entry("doc_intel_read_pdf", "mcp_doc_intel", "read_pdf",
           category="files", description="Extract text from PDF", parallel_ok=True),
    _entry("doc_intel_read_docx", "mcp_doc_intel", "read_docx",
           category="files", description="Extract text from Word DOCX", parallel_ok=True),
    _entry("doc_intel_read_xlsx", "mcp_doc_intel", "read_xlsx",
           category="files", description="Extract data from Excel XLSX", parallel_ok=True),

    # ── Serena (Semantic Code Analysis) ──
    _entry("serena_semantic_search", "mcp_serena", "semantic_search",
           category="refactor", description="Search codebase by semantic intent", parallel_ok=True),
    _entry("serena_find_references", "mcp_serena", "find_references",
           category="refactor", description="Find all references to a symbol", parallel_ok=True),
    _entry("serena_get_symbol_definition", "mcp_serena", "get_symbol_definition",
           category="refactor", description="Get symbol definition with source", parallel_ok=True),
    _entry("serena_get_file_symbols", "mcp_serena", "get_file_symbols",
           category="refactor", description="List all symbols in a file", parallel_ok=True),
    _entry("serena_get_call_hierarchy", "mcp_serena", "get_call_hierarchy",
           category="refactor", description="Show callers/callees for a function", parallel_ok=True),
    _entry("serena_get_inheritance_tree", "mcp_serena", "get_inheritance_tree",
           category="refactor", description="Show class inheritance hierarchy", parallel_ok=True),
    _entry("serena_analyze_import_graph", "mcp_serena", "analyze_import_graph",
           category="refactor", description="Analyze import dependencies", parallel_ok=True),
    _entry("serena_fuzzy_find", "mcp_serena", "fuzzy_find",
           category="refactor", description="Fuzzy-find files and symbols", parallel_ok=True),

    # ── Sequential Thinking ──
    _entry("seqthink_sequential_thinking", "mcp_sequential_think", "sequential_thinking",
           category="think", description="Structured step-by-step reasoning"),
    _entry("seqthink_get_thought_history", "mcp_sequential_think", "get_thought_history",
           category="think", description="Get full thought history", parallel_ok=True),
    _entry("seqthink_think_summary", "mcp_sequential_think", "think_summary",
           category="think", description="Get concise thinking summary", parallel_ok=True),
    _entry("seqthink_clear_session", "mcp_sequential_think", "clear_session",
           category="think", description="Clear thinking session"),
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
