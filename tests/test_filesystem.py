import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
import os
from pathlib import Path
from mcp_filesystem import _norm_allowed, _allowed


class TestNormAllowed:
    def test_adds_backslash(self):
        result = _norm_allowed("C:/Users")
        assert result == "C:\\Users\\"


class TestAllowed:
    def test_cwd_is_allowed(self):
        cwd = os.getcwd() + os.sep
        assert _allowed(cwd)

    def test_nonexistent_path_in_cwd_is_allowed(self):
        assert _allowed(os.path.join(os.getcwd(), "nonexistent_file.txt"))
