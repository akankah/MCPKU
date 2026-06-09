import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_think import _load_session, _detect_stuck, _detect_lag

from mcp_think import _sessions


@pytest.fixture(autouse=True)
def clear_sessions():
    _sessions.clear()


class TestGetSession:
    def test_new_session_creates_empty_list(self):
        result = _load_session("new-session-123")
        assert result == []

    def test_existing_session_returns_same_list(self):
        s1 = _load_session("abc")
        s1.append({"thought": "hello", "step": 1})
        s2 = _load_session("abc")
        assert len(s2) == 1

    def test_default_session(self):
        result = _load_session("default")
        assert result == []


class TestStuckPatternDetector:
    """Verify _detect_stuck triggers websearch demand when model loops."""

    def test_single_thought_not_stuck(self):
        thoughts = [{"step": 1, "thought": "let me try a different approach"}]
        severity, msg = _detect_stuck(thoughts)
        assert severity == ""
        assert msg == ""

    def test_two_retry_thoughts_are_stuck(self):
        thoughts = [
            {"step": 1, "thought": "let me try editing line 5 again"},
            {"step": 2, "thought": "let me try changing the regex flag"},
        ]
        severity, msg = _detect_stuck(thoughts)
        assert severity in ("WARNING", "CRITICAL")
        assert "websearch" in msg.lower() or "search" in msg.lower()

    def test_progress_resets_stuck_counter(self):
        thoughts = [
            {"step": 1, "thought": "let me try again"},
            {"step": 2, "thought": "search result: the issue is X"},
            {"step": 3, "thought": "let me try the fix"},
        ]
        severity, msg = _detect_stuck(thoughts)
        assert severity not in ("WARNING", "CRITICAL")

    def test_mixed_stuck_patterns_still_trigger(self):
        thoughts = [
            {"step": 1, "thought": "maybe this will work"},
            {"step": 2, "thought": "let me try once more"},
        ]
        severity, msg = _detect_stuck(thoughts)
        assert severity in ("WARNING", "CRITICAL")

    def test_stuck_message_mentions_autofallback(self):
        thoughts = [
            {"step": 1, "thought": "coba lagi dengan parameter berbeda"},
            {"step": 2, "thought": "seharusnya ini bisa jalan"},
        ]
        severity, msg = _detect_stuck(thoughts)
        assert severity in ("WARNING", "CRITICAL")
        assert "STUCK" in msg or "loop" in msg.lower()

    def test_empty_thoughts_not_stuck(self):
        severity, msg = _detect_stuck([])
        assert severity == ""

    def test_progress_indicator_in_indonesian(self):
        """Indonesian progress phrases should count as progress."""
        thoughts = [
            {"step": 1, "thought": "coba lagi"},
            {"step": 2, "thought": "berdasarkan dokumentasi, fix-nya begini"},
            {"step": 3, "thought": "let me try the new fix"},
        ]
        severity, msg = _detect_stuck(thoughts)
        assert severity not in ("WARNING", "CRITICAL")


class TestLagDetector:
    """Verify _detect_lag triggers parallel web search demand when think() lags >10s."""

    def test_lag_under_threshold_no_trigger(self):
        thoughts = [{"step": 1, "thought": "let me try again"}]
        msg = _detect_lag(5000, thoughts)
        assert msg == ""

    def test_lag_over_threshold_no_progress_triggers(self):
        thoughts = [{"step": 1, "thought": "let me try editing line 5"}]
        msg = _detect_lag(15_000, thoughts)
        assert "LAG DETECTED" in msg
        assert "parallel" in msg.lower() or "PARALLEL" in msg

    def test_lag_over_threshold_with_progress_no_trigger(self):
        thoughts = [{"step": 1, "thought": "found the docs, applying fix"}]
        msg = _detect_lag(15_000, thoughts)
        assert msg == ""

    def test_lag_exactly_at_threshold_no_trigger(self):
        thoughts = [{"step": 1, "thought": "let me try again"}]
        msg = _detect_lag(10_000, thoughts)
        assert msg == ""

    def test_lag_message_includes_parallel_batch_template(self):
        thoughts = [{"step": 1, "thought": "let me try"}]
        msg = _detect_lag(20_000, thoughts)
        assert "search_web" in msg
        assert "search_stackoverflow" in msg
        assert "think(" in msg
