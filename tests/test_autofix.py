import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from unittest.mock import AsyncMock, patch
from mcp_autofix import (
    _build_fix_commands,
    _can_auto_fix,
    _first_quoted,
    FIX_HANDLERS,
    FIX_STRATEGIES_DESC,
    FIX_SUGGESTIONS,
)


class TestFirstQuoted:
    def test_single_quotes(self):
        assert _first_quoted("No module named 'pandas'") == "pandas"

    def test_double_quotes(self):
        assert _first_quoted('Cannot find module "express"') == "express"

    def test_no_match(self):
        assert _first_quoted("Some random error") is None

    def test_empty_string(self):
        assert _first_quoted("") is None


class TestBuildFixCommands:
    def test_pip_install_for_import_error(self):
        cmds = _build_fix_commands(["Python.ImportError"], "No module named 'flask'")
        assert len(cmds) >= 1
        cmd, desc = cmds[0]
        assert "pip install flask" == cmd

    def test_npm_install_for_js_module(self):
        cmds = _build_fix_commands(["JS.ModuleNotFound"], "Cannot find module 'lodash'")
        assert len(cmds) >= 1
        cmd, _ = cmds[0]
        assert "npm install lodash" == cmd

    def test_unknown_error_no_fix(self):
        cmds = _build_fix_commands(["Python.SyntaxError"], "SyntaxError")
        assert cmds == []

    def test_multiple_errors_deduplicated(self):
        cmds = _build_fix_commands(
            ["Python.ImportError", "Python.ImportError"],
            "No module named 'flask'"
        )
        assert len(cmds) == 1

    def test_no_module_name_fallback(self):
        cmds = _build_fix_commands(["Python.ImportError"], "ImportError: something")
        assert isinstance(cmds, list)

    def test_mkdir_for_filenotfound(self):
        cmds = _build_fix_commands(
            ["Python.FileNotFound"],
            "FileNotFoundError: [Errno 2] No such file or directory: 'src/data/config.json'"
        )
        assert len(cmds) >= 1
        assert any("mkdir" in cmd for cmd, _ in cmds)

    def test_go_mod_tidy(self):
        cmds = _build_fix_commands(["Go.BuildError"], "")
        assert any("go mod tidy" in cmd for cmd, _ in cmds)

    def test_black_for_indentation(self):
        cmds = _build_fix_commands(
            ["Python.IndentationError"],
            '  File "src/app.py", line 42, in <module>\nIndentationError: unexpected indent'
        )
        assert len(cmds) >= 1
        assert any("black" in cmd for cmd, _ in cmds)


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
    def test_all_handlers_have_descriptions(self):
        for etype in FIX_HANDLERS:
            assert etype in FIX_STRATEGIES_DESC, f"{etype} in handlers but missing from descriptions"

    def test_all_handlers_have_suggestions(self):
        for etype in FIX_HANDLERS:
            assert etype in FIX_SUGGESTIONS, f"{etype} in handlers but missing from suggestions"

    def test_handler_is_callable(self):
        for name, handler in FIX_HANDLERS.items():
            assert callable(handler), f"{name} handler not callable"

    def test_handler_returns_list_of_tuples(self):
        for name, handler in FIX_HANDLERS.items():
            result = handler([name], "test error 'foo'", "")
            assert isinstance(result, list), f"{name} handler did not return list"
            if result:
                item = result[0]
                assert isinstance(item, tuple) and len(item) == 2, \
                    f"{name} handler returned non-tuple: {item}"
                assert isinstance(item[0], str) and isinstance(item[1], str), \
                    f"{name} handler returned wrong types"


class TestAutofixRun:
    @pytest.mark.asyncio
    async def test_successful_command(self):
        from mcp_autofix import autofix_run
        with patch("mcp_autofix._run_shell", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "Hello World", "stderr": "", "success": True,
            }
            result = await autofix_run("echo hello", max_retries=1)
            assert "✅ Command succeeded" in result

    @pytest.mark.asyncio
    async def test_autofix_fix_then_retry(self):
        from mcp_autofix import autofix_run
        call_count = [0]

        async def mock_shell(command, cwd, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 1, "stdout": "", "stderr": "ModuleNotFoundError: No module named 'pandas'", "success": False}
            elif call_count[0] == 2:
                return {"exit_code": 0, "stdout": "Successfully installed pandas", "stderr": "", "success": True}
            else:
                return {"exit_code": 0, "stdout": "app.py ran successfully", "stderr": "", "success": True}

        with patch("mcp_autofix._run_shell", side_effect=mock_shell):
            result = await autofix_run("python app.py", max_retries=2)
            assert "✅ Command succeeded" in result

    @pytest.mark.asyncio
    async def test_unfixable_error_gives_suggestion(self):
        from mcp_autofix import autofix_run
        with patch("mcp_autofix._run_shell", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "exit_code": 1, "stdout": "", "stderr": "SyntaxError: invalid syntax", "success": False,
            }
            result = await autofix_run("python bad.py", max_retries=1)
            assert "Cannot auto-fix" in result or "No automatic fix" in result

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        from mcp_autofix import autofix_run
        call_count = [0]

        async def mock_shell(command, cwd, timeout):
            call_count[0] += 1
            if "pip install" in command:
                return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}
            return {"exit_code": 1, "stdout": "", "stderr": "ModuleNotFoundError: No module named 'x'", "success": False}

        with patch("mcp_autofix._run_shell", side_effect=mock_shell):
            result = await autofix_run("python fail.py", max_retries=1)
            assert "Max retries" in result

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

    @pytest.mark.asyncio
    async def test_strategies_tool(self):
        from mcp_autofix import autofix_strategies
        result = await autofix_strategies()
        assert "pip install" in result

    @pytest.mark.asyncio
    async def test_autofix_with_go_mod_tidy(self):
        from mcp_autofix import autofix_run
        call_count = [0]

        async def mock_shell(command, cwd, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 1, "stdout": "", "stderr": "main.go:5:2: error: undefined: x", "success": False}
            elif call_count[0] == 2:
                return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}
            else:
                return {"exit_code": 0, "stdout": "build succeeded", "stderr": "", "success": True}

        with patch("mcp_autofix._run_shell", side_effect=mock_shell):
            result = await autofix_run("go build", max_retries=1)
            assert "✅ Command succeeded" in result
