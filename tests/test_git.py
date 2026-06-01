import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_git import _reject_flag
from git.exc import BadName


class TestRejectFlag:
    def test_rejects_dash_prefix(self):
        with pytest.raises(BadName):
            _reject_flag("--dangerous", "flag")

    def test_rejects_single_dash(self):
        with pytest.raises(BadName):
            _reject_flag("-rf", "flag")

    def test_allows_normal_value(self):
        _reject_flag("main", "branch")  # should not raise

    def test_allows_none(self):
        _reject_flag(None, "param")  # should not raise

    def test_allows_empty(self):
        _reject_flag("", "param")  # should not raise
