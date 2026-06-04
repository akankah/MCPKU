import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_think import _get_session, _detect_stuck

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


class TestStuckPatternDetector:
    """Verify _detect_stuck triggers websearch demand when model loops."""

    def test_single_thought_not_stuck(self):
        thoughts = [{"step": 1, "thought": "let me try a different approach"}]
        is_stuck, msg = _detect_stuck(thoughts)
        assert is_stuck is False
        assert msg == ""

    def test_two_retry_thoughts_are_stuck(self):
        thoughts = [
            {"step": 1, "thought": "let me try editing line 5 again"},
            {"step": 2, "thought": "let me try changing the regex flag"},
        ]
        is_stuck, msg = _detect_stuck(thoughts)
        assert is_stuck is True
        assert "websearch" in msg.lower() or "AUTOFALLBACK" in msg

    def test_progress_resets_stuck_counter(self):
        thoughts = [
            {"step": 1, "thought": "let me try again"},
            {"step": 2, "thought": "search result: the issue is X"},
            {"step": 3, "thought": "let me try the fix"},
        ]
        is_stuck, msg = _detect_stuck(thoughts)
        assert is_stuck is False

    def test_mixed_stuck_patterns_still_trigger(self):
        thoughts = [
            {"step": 1, "thought": "maybe this will work"},
            {"step": 2, "thought": "let me try once more"},
        ]
        is_stuck, msg = _detect_stuck(thoughts)
        assert is_stuck is True

    def test_stuck_message_mentions_autofallback(self):
        thoughts = [
            {"step": 1, "thought": "coba lagi dengan parameter berbeda"},
            {"step": 2, "thought": "seharusnya ini bisa jalan"},
        ]
        is_stuck, msg = _detect_stuck(thoughts)
        assert is_stuck is True
        assert "AUTOFALLBACK" in msg

    def test_empty_thoughts_not_stuck(self):
        is_stuck, msg = _detect_stuck([])
        assert is_stuck is False

    def test_progress_indicator_in_indonesian(self):
        """Indonesian progress phrases should count as progress."""
        thoughts = [
            {"step": 1, "thought": "coba lagi"},
            {"step": 2, "thought": "berdasarkan dokumentasi, fix-nya begini"},
            {"step": 3, "thought": "let me try the new fix"},
        ]
        is_stuck, msg = _detect_stuck(thoughts)
        assert is_stuck is False
