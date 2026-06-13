import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from mcp_manifest import (
    ToolEntry,
    TOOL_MANIFEST,
    get_tool,
    get_tools_by_category,
    get_categories,
    CATEGORY_TOOLS,
)


class TestToolEntry:
    def test_minimal_entry(self):
        entry = ToolEntry(name="foo", module="mcp_web", func_name="search_web")
        assert entry.name == "foo"
        assert entry.category == "general"
        assert entry.dangerous is False

    def test_get_func_resolves_lazily(self):
        entry = ToolEntry(name="bar", module="mcp_time", func_name="get_current_time")
        func = entry.get_func()
        import inspect
        assert inspect.isfunction(func) or inspect.iscoroutinefunction(func)

    def test_get_func_caches(self):
        entry = ToolEntry(name="baz", module="mcp_time", func_name="get_current_time")
        f1 = entry.get_func()
        f2 = entry.get_func()
        assert f1 is f2

    def test_get_func_raises_on_bad_module(self):
        entry = ToolEntry(name="bad", module="does_not_exist", func_name="foo")
        with pytest.raises((ModuleNotFoundError, ImportError)):
            entry.get_func()

    def test_get_params_reflects_signature(self):
        import mcp_time
        entry = ToolEntry(name="t", module="mcp_time", func_name="get_current_time")
        params = entry.get_params()
        assert isinstance(params, list)
        assert any(p["name"] == "timezone" for p in params)

    def test_get_params_skips_self_cls(self):
        entry = ToolEntry(name="t", module="mcp_time", func_name="get_current_time")
        params = entry.get_params()
        names = [p["name"] for p in params]
        assert "self" not in names
        assert "cls" not in names

    def test_dangerous_default_false(self):
        entry = ToolEntry(name="safe", module="mcp_web", func_name="search_web")
        assert entry.dangerous is False

    def test_full_entry_kwargs(self):
        entry = ToolEntry(
            name="full", module="mcp_autofix", func_name="autofix_run",
            category="debug", dangerous=True, requires_repo=False,
            requires_network=True, timeout_suggestion=120, parallel_ok=False,
        )
        assert entry.category == "debug"
        assert entry.dangerous is True
        assert entry.requires_network is True
        assert entry.timeout_suggestion == 120


class TestTOOL_MANIFEST:
    def test_manifest_is_dict(self):
        assert isinstance(TOOL_MANIFEST, dict)

    def test_manifest_has_entries(self):
        assert len(TOOL_MANIFEST) > 50

    def test_manifest_all_entries_are_tool_entry(self):
        for v in TOOL_MANIFEST.values():
            assert isinstance(v, ToolEntry)

    def test_manifest_has_research_category(self):
        names = CATEGORY_TOOLS.get("research", [])
        assert len(names) >= 10

    def test_manifest_key_matches_entry_name(self):
        for key, entry in TOOL_MANIFEST.items():
            assert key == entry.name

    def test_get_tool_returns_entry(self):
        entry = get_tool("web_search_web")
        assert entry is not None
        assert entry.name == "web_search_web"

    def test_get_tool_nonexistent(self):
        assert get_tool("does_not_exist_12345") is None

    def test_get_tools_by_category(self):
        tools = get_tools_by_category("memory")
        assert len(tools) > 0
        assert all(t.category == "memory" for t in tools)

    def test_get_categories(self):
        cats = get_categories()
        assert "research" in cats
        assert "memory" in cats
        assert "git" in cats
        assert "bash" in cats
        assert all(isinstance(c, str) for c in cats)

    def test_dangerous_tools_exist(self):
        dangerous = [e for e in TOOL_MANIFEST.values() if e.dangerous]
        assert len(dangerous) > 5

    def test_tools_with_network(self):
        networked = [e for e in TOOL_MANIFEST.values() if e.requires_network]
        assert len(networked) >= 16

    def test_no_tool_without_module(self):
        for e in TOOL_MANIFEST.values():
            assert e.module != ""
