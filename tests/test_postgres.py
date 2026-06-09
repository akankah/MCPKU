import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import psycopg2
from mcp_postgres import _retry_sync


class TestRetrySync:
    def test_success_on_first_try(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return "success"

        result = _retry_sync(fn, retries=3, backoff=0.01)
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure_then_success(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                import psycopg2
                raise psycopg2.OperationalError("transient error")
            return "success"

        result = _retry_sync(fn, retries=3, backoff=0.01)
        assert result == "success"
        assert call_count == 3

    def test_give_up_after_all_retries(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            import psycopg2
            raise psycopg2.OperationalError("persistent error")

        with pytest.raises(psycopg2.OperationalError):
            _retry_sync(fn, retries=2, backoff=0.01)
        assert call_count == 2

    def test_does_not_retry_on_non_transient_error(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("non-transient error")

        with pytest.raises(ValueError):
            _retry_sync(fn, retries=3, backoff=0.01)
        assert call_count == 1
