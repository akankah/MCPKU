import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import os
import pytest
from pathlib import Path
from unittest import mock

import verify_setup


class TestStripJsoncComments:
    def test_removes_line_comment(self):
        text = '{\n  "a": 1, // hello\n  "b": 2\n}'
        result = verify_setup._strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_removes_block_comment(self):
        text = '{\n  "a": 1, /* hello */\n  "b": 2\n}'
        result = verify_setup._strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_preserves_url_with_double_slash(self):
        # URLs with // should NOT be stripped
        text = '{\n  "baseURL": "http://localhost:9080/v1"\n}'
        result = verify_setup._strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed["baseURL"] == "http://localhost:9080/v1"


class TestCheckPaths:
    def test_valid_python_path(self, tmp_path):
        server_file = tmp_path / "mcp_test.py"
        server_file.write_text("# fake")
        servers = {
            "test": {"command": ["python", str(server_file)], "enabled": True}
        }
        broken = verify_setup.check_paths(servers)
        assert broken == []

    def test_missing_python_file(self):
        servers = {
            "broken": {"command": ["python", "E:/nonexistent/mcp_broken.py"]}
        }
        broken = verify_setup.check_paths(servers)
        assert len(broken) == 1
        assert broken[0][0] == "broken"

    def test_no_command(self):
        servers = {"empty": {}}
        broken = verify_setup.check_paths(servers)
        assert len(broken) == 1
        assert broken[0][1] == "no command"


class TestMainDispatch:
    def test_no_args_returns_1(self, capsys):
        with mock.patch("sys.argv", ["verify_setup.py"]):
            result = verify_setup.main()
        assert result == 1
        captured = capsys.readouterr()
        assert "Usage" in captured.out or "verify_setup" in captured.out

    def test_unknown_command_returns_1(self):
        with mock.patch("sys.argv", ["verify_setup.py", "nope"]):
            result = verify_setup.main()
        assert result == 1


class TestExpectedServers:
    """The canonical 21-server set must include the core tools."""

    def test_all_core_servers_present(self):
        assert "bash" in verify_setup.EXPECTED_SERVERS
        assert "think" in verify_setup.EXPECTED_SERVERS
        assert "memory" in verify_setup.EXPECTED_SERVERS
        assert "autofix" in verify_setup.EXPECTED_SERVERS
        assert "diagnostics" in verify_setup.EXPECTED_SERVERS

    def test_count_is_21(self):
        assert len(verify_setup.EXPECTED_SERVERS) == 21
