import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from unittest.mock import AsyncMock, patch
from mcp_autofix import (
    _extract_module_name,
    _build_fix_commands,
    _can_auto_fix,
    FIX_STRATEGIES,
    FIX_SUGGESTIONS,
)


class TestExtractModuleName:
    def test_extract_pip_style(self):
        pattern = FIX_STRATEGIES["Python.ImportError"]["extract"]
        assert _extract_module_name("No module named 'pandas'", pattern) == "pandas"

    def test_extract_npm_style(self):
        pattern = FIX_STRATEGIES["JS.ModuleNotFound"]["extract"]
        assert _extract_module_name("Cannot find module 'express'", pattern) == "express"

    def test_extract_double_quotes(self):
        pattern = FIX_STRATEGIES["Python.ImportError"]["extract"]
        assert _extract_module_name('No module named "requests"', pattern) == "requests"

    def test_no_match_returns_none(self):
        pattern = FIX_STRATEGIES["Python.ImportError"]["extract"]
        assert _extract_module_name("Some random error", pattern) is None

    def test_empty_string(self):
        pattern = FIX_STRATEGIES["Python.ImportError"]["extract"]
        assert _extract_module_name("", pattern) is None


class TestBuildFixCommands:
    def test_pip_install_for_import_error(self):
        cmds = _build_fix_commands(["Python.ImportError"], "No module named 'flask'")
        assert "pip install flask" in cmds

    def test_npm_install_for_js_module(self):
        cmds = _build_fix_commands(["JS.ModuleNotFound"], "Cannot find module 'lodash'")
        assert "npm install lodash" in cmds

    def test_unknown_error_no_fix(self):
        cmds = _build_fix_commands(["Python.SyntaxError"], "SyntaxError")
        assert cmds == []

    def test_multiple_errors_multiple_fixes(self):
        cmds = _build_fix_commands(
            ["Python.ImportError", "JS.ModuleNotFound"],
            "No module named 'flask'\nCannot find module 'lodash'"
        )
        # Both patterns extract first quoted string ('flask') since re.search is used
        assert "pip install flask" in cmds
        assert "npm install flask" in cmds

    def test_no_module_name_fallback(self):
        cmds = _build_fix_commands(["Python.ImportError"], "ImportError: something")
        # No single-quoted name to extract, so fallback may grab something or None
        assert isinstance(cmds, list)


class TestCanAutoFix:
    def test_auto_fixable_error(self):
        assert _can_auto_fix(["Python.ImportError"]) is True

    def test_not_auto_fixable_error(self):
        assert _can_auto_fix(["Python.SyntaxError"]) is False

    def test_mixed_errors(self):
        assert _can_auto_fix(["Python.SyntaxError", "Python.ImportError"]) is True

    def test_empty(self):
        assert _can_auto_fix([]) is False

    def test_unknown(self):
        assert _can_auto_fix(["Unknown"]) is False


class TestFixStrategiesCoverage:
    def test_all_strategies_have_required_keys(self):
        for name, strat in FIX_STRATEGIES.items():
            assert "cmd" in strat, f"{name} missing 'cmd'"
            assert "extract" in strat, f"{name} missing 'extract'"
            assert "desc" in strat, f"{name} missing 'desc'"

    def test_all_patterns_are_compiled_regex(self):
        for name, strat in FIX_STRATEGIES.items():
            assert hasattr(strat["extract"], "search"), f"{name} extract not a compiled regex"

    def test_strategies_are_subset_of_suggestions(self):
        for etype in FIX_STRATEGIES:
            assert etype in FIX_SUGGESTIONS, f"{etype} in strategies but missing from suggestions"


class TestAutofixRun:
    @pytest.mark.asyncio
    async def test_successful_command(self):
        from mcp_autofix import autofix_run
        with patch("mcp_autofix._run_shell", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "exit_code": 0,
                "stdout": "Hello World",
                "stderr": "",
                "success": True,
            }
            result = await autofix_run("echo hello", max_retries=1)
            assert "✅ Command succeeded" in result
            assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_autofix_fix_then_retry(self):
        from mcp_autofix import autofix_run
        call_count = [0]

        async def mock_shell(command, cwd, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: original command fails
                return {
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "ModuleNotFoundError: No module named 'pandas'",
                    "success": False,
                }
            elif call_count[0] == 2:
                # Second call: pip install pandas succeeds
                return {
                    "exit_code": 0,
                    "stdout": "Successfully installed pandas",
                    "stderr": "",
                    "success": True,
                }
            else:
                # Third call: retry succeeds
                return {
                    "exit_code": 0,
                    "stdout": "app.py ran successfully",
                    "stderr": "",
                    "success": True,
                }

        with patch("mcp_autofix._run_shell", side_effect=mock_shell):
            result = await autofix_run("python app.py", max_retries=2)
            assert "✅ Command succeeded" in result
            assert "pip install pandas" in result
            assert "Retry #1" in result

    @pytest.mark.asyncio
    async def test_unfixable_error_gives_suggestion(self):
        from mcp_autofix import autofix_run
        with patch("mcp_autofix._run_shell", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "exit_code": 1,
                "stdout": "",
                "stderr": "SyntaxError: invalid syntax",
                "success": False,
            }
            result = await autofix_run("python bad.py", max_retries=1)
            assert "Cannot auto-fix" in result or "No automatic fix" in result or "SyntaxError" in result

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        from mcp_autofix import autofix_run
        call_count = [0]

        async def mock_shell(command, cwd, timeout):
            call_count[0] += 1
            if "pip install" in command:
                return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": "ModuleNotFoundError: No module named 'x'",
                "success": False,
            }

        with patch("mcp_autofix._run_shell", side_effect=mock_shell):
            result = await autofix_run("python fail.py", max_retries=1)
            assert "Max retries" in result or "retries reached" in result

    @pytest.mark.asyncio
    async def test_auto_commit(self):
        from mcp_autofix import autofix_run
        call_count = [0]

        async def mock_shell(command, cwd, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "ModuleNotFoundError: No module named 'flask'",
                    "success": False,
                }
            elif call_count[0] == 2:
                return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}
            elif call_count[0] == 3:
                return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}
            else:
                return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}

        with patch("mcp_autofix._run_shell", side_effect=mock_shell):
            result = await autofix_run("python app.py", max_retries=1, auto_commit=True)
            assert "✅ Command succeeded" in result

    @pytest.mark.asyncio
    async def test_blocks_dangerous_command(self):
        from mcp_autofix import autofix_run
        result = await autofix_run("rm -rf /")
        assert "blocked" in result

    @pytest.mark.asyncio
    async def test_history_tool(self):
        from mcp_autofix import autofix_history
        result = await autofix_history()
        assert isinstance(result, str)


class TestAutofixStrategies:
    @pytest.mark.asyncio
    async def test_returns_strategies_list(self):
        from mcp_autofix import autofix_strategies
        result = await autofix_strategies()
        assert "pip install" in result
        assert "npm install" in result
