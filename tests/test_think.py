import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_think import _get_session

# Import _sessions directly to clear between tests
from mcp_think import _sessions


@pytest.fixture(autouse=True)
def clear_sessions():
    _sessions.clear()


class TestGetSession:
    def test_new_session_creates_empty_list(self):
        result = _get_session("new-session-123")
        assert result == []

    def test_existing_session_returns_same_list(self):
        s1 = _get_session("abc")
        s1.append({"thought": "hello", "step": 1})
        s2 = _get_session("abc")
        assert len(s2) == 1

    def test_default_session(self):
        result = _get_session("")
        new_id = list(_sessions.keys())[0] if _sessions else None
        assert len(_sessions) == 1
