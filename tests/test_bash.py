import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_bash import _check_command


class TestCheckCommand:
    def test_allowed_python(self):
        assert _check_command("python script.py") == ""

    def test_allowed_npm(self):
        assert _check_command("npm run build") == ""

    def test_allowed_pip(self):
        assert _check_command("pip install requests") == ""

    def test_allowed_git(self):
        assert _check_command("git status") == ""

    def test_allowed_git_log(self):
        assert _check_command("git log --oneline") == ""

    def test_git_blocked_subcommand(self):
        result = _check_command("git filter-branch")
        assert result != ""

    def test_blocked_unknown_command(self):
        result = _check_command("rm -rf /")
        assert result != ""

    def test_blocked_del(self):
        result = _check_command("del /f *.txt")
        assert result != ""

    def test_blocked_subshell(self):
        result = _check_command("echo $(rm -rf /)")
        assert result != ""

    def test_blocked_backtick(self):
        result = _check_command("echo `rm -rf /`")
        assert result != ""

    def test_blocked_format(self):
        result = _check_command("format C:")
        assert result != ""

    def test_empty_command(self):
        result = _check_command("")
        assert result != ""

    def test_blocked_dangerous_flag(self):
        result = _check_command("chmod --no-preserve-root 777 /")
        assert result != ""

    def test_blocked_shutdown(self):
        result = _check_command("shutdown /s")
        assert result != ""

    def test_blocked_wildcard_delete(self):
        result = _check_command("del *.*")
        assert result != ""
