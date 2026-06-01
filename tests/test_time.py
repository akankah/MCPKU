import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_time import _resolve_tz


class TestResolveTz:
    def test_valid_timezone(self):
        tz = _resolve_tz("Asia/Jakarta")
        assert tz.key == "Asia/Jakarta"

    def test_valid_timezone_utc(self):
        tz = _resolve_tz("UTC")
        assert tz.key == "UTC"

    def test_invalid_timezone_raises(self):
        with pytest.raises(ValueError):
            _resolve_tz("Mars/Olympus")

    def test_none_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _resolve_tz(None)
