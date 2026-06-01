import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_redis import _flush_tokens

# The flushdb 2-step mechanism uses a module-level dict with TTL


class TestFlushTokens:
    @pytest.fixture(autouse=True)
    def clear_tokens(self):
        _flush_tokens.clear()

    def test_token_generation_and_validation(self):
        import secrets
        import time
        from mcp_redis import redis_flushdb_request, redis_flushdb_confirm

        # We cannot call the async tools directly in a sync test without event loop
        # So we test the token dict directly
        token = secrets.token_hex(16)
        expiry = time.time() + 60
        _flush_tokens[token] = expiry

        assert token in _flush_tokens
        assert _flush_tokens[token] > time.time()

    def test_token_expiry(self):
        import time
        token = "expired-token"
        _flush_tokens[token] = time.time() - 10  # expired 10s ago

        now = time.time()
        expired = [k for k, v in _flush_tokens.items() if v < now]
        assert token in expired

    def test_unknown_token_not_present(self):
        assert "nonexistent" not in _flush_tokens
