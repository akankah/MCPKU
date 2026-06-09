import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

import pytest

import mcp_cache


def _reset_cache():
    """Reset mcp_cache._cache to force re-init in each test."""
    mcp_cache._cache = None


@pytest.fixture(autouse=True)
def reset():
    _reset_cache()


class TestNormalizeKey:
    def test_short_key_unchanged(self):
        assert mcp_cache._normalize_key("hello") == "hello"

    def test_long_key_hashes(self):
        long_key = "x" * 250
        result = mcp_cache._normalize_key(long_key)
        assert result.startswith("hash:")
        assert len(result) == 5 + 32

    def test_boundary_200(self):
        key = "a" * 200
        assert mcp_cache._normalize_key(key) == key

    def test_boundary_201(self):
        key = "a" * 201
        result = mcp_cache._normalize_key(key)
        assert result.startswith("hash:")


class TestGetRedis:
    def test_returns_none_when_redis_unavailable(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache._get_redis() is None

    def test_singleton_stays_none(self):
        """After failed connection, _cache stays False => get_redis returns None."""
        real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __builtins__['__import__']
        def fake_import(name, *args, **kwargs):
            if name == 'redis':
                raise ImportError("no redis module")
            return real_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=fake_import):
            r = mcp_cache._get_redis()
            assert r is None
            r2 = mcp_cache._get_redis()
            assert r2 is None


class TestCacheGet:
    def test_returns_none_when_disabled(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache.cache_get("key") is None

    def test_returns_value(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = "cached_value"
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_get("mykey") == "cached_value"
        mock_redis.get.assert_called_once_with("mykey")

    def test_normalizes_long_key(self):
        mock_redis = MagicMock()
        long_key = "x" * 250
        with patch.object(mcp_cache, "_cache", mock_redis):
            mcp_cache.cache_get(long_key)
        call_arg = mock_redis.get.call_args[0][0]
        assert call_arg.startswith("hash:")

    def test_handles_exception_gracefully(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("connection lost")
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_get("key") is None


class TestCacheSet:
    def test_returns_false_when_disabled(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache.cache_set("key", "val") is False

    def test_calls_setex(self):
        mock_redis = MagicMock()
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_set("k", "v", ttl=60) is True
        mock_redis.setex.assert_called_once_with("k", 60, "v")

    def test_default_ttl_is_3600(self):
        mock_redis = MagicMock()
        with patch.object(mcp_cache, "_cache", mock_redis):
            mcp_cache.cache_set("k", "v")
        mock_redis.setex.assert_called_once_with("k", 3600, "v")

    def test_normalizes_long_key(self):
        mock_redis = MagicMock()
        long_key = "x" * 250
        with patch.object(mcp_cache, "_cache", mock_redis):
            mcp_cache.cache_set(long_key, "v")
        call_arg = mock_redis.setex.call_args[0][0]
        assert call_arg.startswith("hash:")

    def test_handles_exception_gracefully(self):
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("timeout")
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_set("k", "v") is False


class TestCacheDelete:
    def test_returns_false_when_disabled(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache.cache_delete("key") is False

    def test_calls_delete(self):
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_delete("k") is True
        mock_redis.delete.assert_called_once_with("k")

    def test_returns_false_when_key_missing(self):
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 0
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_delete("missing") is False

    def test_handles_exception_gracefully(self):
        mock_redis = MagicMock()
        mock_redis.delete.side_effect = Exception("error")
        with patch.object(mcp_cache, "_cache", mock_redis):
            assert mcp_cache.cache_delete("k") is False


class TestSilentDegradation:
    """When Redis is absent, all calls should degrade silently (no crash)."""

    def test_get_no_redis(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache.cache_get("k") is None

    def test_set_no_redis(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache.cache_set("k", "v") is False

    def test_delete_no_redis(self):
        with patch.object(mcp_cache, "_cache", None):
            with patch("mcp_cache._get_redis", return_value=None):
                assert mcp_cache.cache_delete("k") is False
