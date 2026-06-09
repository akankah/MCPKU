"""Tests for web/ package + mcp_web.py entry point."""

import json
import sys, os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.parsers import html_to_text, json_ok, json_error
from web.cache import get as cache_get, set as cache_set
from web.search import _format_question, _format_answer


def _mock_http_response(text="", status_code=200):
    """Build a mock HTTP response object that httpx code can use safely.
    
    MagicMock auto-creates attributes as mocks. For httpx.Response, we need
    text as a real string, status_code as an int, and raise_for_status as a
    regular synchronous callable (NOT a mock) to avoid coroutine warnings.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = lambda: None
    return resp


def _mock_http_client(resp):
    """Build an async mock client for httpx.AsyncClient context manager pattern.
    async with httpx.AsyncClient() as client:  →  __aenter__ must return client.
    """
    client = AsyncMock()
    client.__aenter__.return_value = client  # async with returns self
    client.__aexit__ = AsyncMock(return_value=None)
    client.get = AsyncMock(return_value=resp)
    return client


# ==============================================================================
# parsers.py
# ==============================================================================

class TestHtmlToText:
    def test_strips_tags(self):
        assert "hello world" in html_to_text("<html><body><p>hello world</p></body></html>")

    def test_extracts_links(self):
        result = html_to_text('<a href="https://example.com">click here</a>')
        assert "click here" in result

    def test_empty_html(self):
        assert html_to_text("") == ""

    def test_plain_text(self):
        assert html_to_text("just text") == "just text"

    def test_line_breaks(self):
        result = html_to_text("<p>line1</p><p>line2</p>")
        assert "line1" in result
        assert "line2" in result

    def test_scripts_stripped(self):
        result = html_to_text("<script>alert('xss');</script>hello")
        assert "hello" in result
        assert "script" not in result

    def test_styles_stripped(self):
        result = html_to_text("<style>.red{color:red}</style>text")
        assert "text" in result
        assert "red" not in result.split("text")[0]

    def test_nested_tags(self):
        result = html_to_text("<div><p><b>bold</b> and <i>italic</i></p></div>")
        assert "bold and italic" in result

    def test_html_entities_unescaped(self):
        result = html_to_text("&amp; &lt; &gt; &quot;")
        assert "& < >" in result or "& < > \"" in result

    def test_non_ascii(self):
        result = html_to_text("<p>café résumé 中文</p>")
        assert "café" in result
        assert "résumé" in result
        assert "中文" in result

    def test_multiple_links_stripped(self):
        result = html_to_text('<a href="https://a.com">A</a> and <a href="https://b.com">B</a>')
        assert "A" in result
        assert "B" in result

    def test_short_lines_filtered(self):
        result = html_to_text("<p>ab</p><p>cd</p>")
        assert result == ""

    def test_br_becomes_newline(self):
        result = html_to_text("line1<br>line2<br/>line3")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_img_alt_extracted(self):
        result = html_to_text('<img alt="photo of a cat" src="cat.jpg">')
        assert "photo of a cat" in result

    def test_very_long_input_collapses_whitespace(self):
        long = "<p>" + "a" * 100 + "   " + "b" * 100 + "</p>"
        result = html_to_text(long)
        assert "  " not in result

    def test_mixed_tags_and_text(self):
        result = html_to_text("before<div>inside</div>after")
        assert "before" in result
        assert "inside" in result
        assert "after" in result

    def test_heading_tags_add_newlines(self):
        result = html_to_text("<h1>Title here</h1><h2>Sub title</h2>")
        assert "Title here" in result
        assert "Sub title" in result

    def test_dedup_similar_lines(self):
        result = html_to_text("<p>hello world</p><p>hello world</p>")
        assert result.count("hello world") == 1


class TestJsonOk:
    def test_basic_structure(self):
        result = json_ok("test_tool", {"key": "val"})
        assert result == {"success": True, "tool": "test_tool", "data": {"key": "val"}}

    def test_with_meta(self):
        result = json_ok("test_tool", "data", {"source": "web"})
        assert result["meta"] == {"source": "web"}

    def test_none_meta_excluded(self):
        result = json_ok("test_tool", "data")
        assert "meta" not in result

    def test_list_data(self):
        result = json_ok("search", [1, 2, 3])
        assert result["data"] == [1, 2, 3]

    def test_string_data(self):
        result = json_ok("fetch", "content")
        assert result["data"] == "content"


class TestJsonError:
    def test_basic_structure(self):
        result = json_error("test_tool", "something broke")
        assert result == {"success": False, "tool": "test_tool", "error": "something broke"}

    def test_with_detail(self):
        result = json_error("test_tool", "not found", "resource id=5")
        assert result["detail"] == "resource id=5"

    def test_empty_detail_excluded(self):
        result = json_error("test_tool", "error")
        assert "detail" not in result


# ==============================================================================
# cache.py
# ==============================================================================

class TestCache:
    @patch("web.cache._get", return_value="cached_value")
    def test_get_returns_value(self, mock_get):
        assert cache_get("mykey") == "cached_value"
        mock_get.assert_called_once_with("mykey")

    @patch("web.cache._get", return_value=None)
    def test_get_returns_none_for_missing(self, mock_get):
        assert cache_get("missing") is None

    @patch("web.cache._get")
    def test_get_string_key(self, mock_get):
        cache_get("string_key")
        mock_get.assert_called_once_with("string_key")

    @patch("web.cache._set")
    def test_set_calls_with_default_ttl(self, mock_set):
        cache_set("key", "value")
        mock_set.assert_called_once_with("key", "value", ttl=1800)

    @patch("web.cache._set")
    def test_set_custom_ttl(self, mock_set):
        cache_set("key", "value", ttl=3600)
        mock_set.assert_called_once_with("key", "value", ttl=3600)


# ==============================================================================
# fetch.py
# ==============================================================================

class TestFetchUrl:
    """fetch_url(url, max_length=5000, start_index=0, raw=False)."""

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_url_normalization(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("hello world"))
        from web.fetch import fetch_url
        result = await fetch_url("example.com")
        assert result["success"] is True
        call_url = mock_http.return_value.get.call_args[0][0]
        assert call_url.startswith("https://")

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_https_preserved(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("content"))
        from web.fetch import fetch_url
        await fetch_url("https://already-https.com")
        call_url = mock_http.return_value.get.call_args[0][0]
        assert call_url == "https://already-https.com"

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_max_length_truncation(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("x" * 10000))
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com", max_length=100)
        assert len(result["data"]) < 200
        assert "truncated" in result["data"]

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_start_index(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("hello world test"))
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com", start_index=6)
        assert "world" in result["data"]

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_raw_mode(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(
            _mock_http_response("<html><body>raw content</body></html>")
        )
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com", raw=True)
        assert "<html>" in result["data"]

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get")
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_cache_hit(self, mock_http, mock_set, mock_get):
        mock_get.return_value = "cached content"
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com")
        assert result["data"] == "cached content"
        assert result["meta"]["cached"] is True

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_nocache_bypass(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("fresh content"))
        mock_get.return_value = "stale content"
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com?nocache=true")
        assert result["data"] == "fresh content"
        assert result["meta"]["cached"] is False

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_http_error(self, mock_http, mock_set, mock_get):
        from httpx import HTTPStatusError
        resp = _mock_http_response("error", status_code=500)
        mock_req = MagicMock()
        resp.raise_for_status = MagicMock(
            side_effect=HTTPStatusError("500", request=mock_req, response=resp)
        )
        mock_http.return_value = _mock_http_client(resp)
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com")
        assert result["success"] is False
        assert result["tool"] == "fetch_url"

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_timeout_error(self, mock_http, mock_set, mock_get):
        from httpx import TimeoutException
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(side_effect=TimeoutException("request timed out"))
        mock_http.return_value = client
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com")
        assert result["success"] is False
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_cache_set_on_success(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("content"))
        from web.fetch import fetch_url
        await fetch_url("https://example.com")
        assert mock_set.called

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_error_does_not_cache(self, mock_http, mock_set, mock_get):
        client = AsyncMock()
        client.get.side_effect = RuntimeError("network down")
        mock_http.return_value = client
        from web.fetch import fetch_url
        await fetch_url("https://example.com")
        assert not mock_set.called

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_passes_headers(self, mock_http, mock_set, mock_get):
        mock_http.return_value = _mock_http_client(_mock_http_response("ok"))
        from web.fetch import fetch_url
        await fetch_url("https://example.com")
        call_headers = mock_http.return_value.get.call_args[1]["headers"]
        assert "User-Agent" in call_headers
        assert "Accept" in call_headers

    @pytest.mark.asyncio
    @patch("web.fetch.cache_get", return_value=None)
    @patch("web.fetch.cache_set")
    @patch("web.fetch.httpx.AsyncClient")
    async def test_connection_error(self, mock_http, mock_set, mock_get):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(side_effect=ConnectionError("connection refused"))
        mock_http.return_value = client
        from web.fetch import fetch_url
        result = await fetch_url("https://example.com")
        assert result["success"] is False
        assert "connection" in result["error"].lower()


# ==============================================================================
# search.py
# ==============================================================================

class TestFormatQuestion:
    def test_basic_fields(self):
        item = {
            "title": "How to test in Python?",
            "link": "https://stackoverflow.com/q/12345",
            "score": 42,
            "answer_count": 3,
            "accepted_answer_id": 999,
            "tags": ["python", "testing"],
            "owner": {"display_name": "user1"},
        }
        result = _format_question(item)
        assert "How to test in Python?" in result
        assert "42 votes" in result
        assert "3 answers" in result
        assert "✓" in result
        assert "python, testing" in result
        assert "user1" in result

    def test_missing_fields(self):
        item = {"title": "No metadata"}
        result = _format_question(item)
        assert "No metadata" in result
        assert "0 votes" in result
        assert "anonymous" in result


class TestFormatAnswer:
    def test_basic_fields(self):
        item = {
            "score": 10,
            "is_accepted": True,
            "owner": {"display_name": "expert"},
            "body": "<p>Use <code>pytest</code></p>",
        }
        result = _format_answer(item)
        assert "10 votes" in result
        assert "✓ ACCEPTED" in result
        assert "expert" in result
        assert "pytest" in result
        assert "<code>" not in result

    def test_no_owner(self):
        item = {"score": 0, "is_accepted": False, "body": "simple answer"}
        result = _format_answer(item)
        assert "anonymous" in result
        assert "simple answer" in result


class TestSearchStackOverflow:
    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_success(self, mock_set, mock_get, mock_stackex):
        mock_stackex.return_value = {
            "items": [{
                "title": "Python question",
                "link": "https://stackoverflow.com/q/1",
                "score": 10, "answer_count": 2,
                "tags": ["python"], "owner": {"display_name": "u1"},
            }],
            "quota_remaining": 999,
            "total": 1,
        }
        from web.search import search_stackoverflow
        result = await search_stackoverflow("python")
        assert result["success"] is True
        assert "Python question" in result["data"]
        assert result["meta"]["quota_remaining"] == 999

    @pytest.mark.asyncio
    @patch("web.search._stackex_get", return_value=None)
    @patch("web.search.cache_get", return_value=None)
    async def test_api_error(self, mock_get, mock_stackex):
        from web.search import search_stackoverflow
        result = await search_stackoverflow("query")
        assert result["success"] is False
        assert "API error" in result["error"]

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_empty_results(self, mock_set, mock_get, mock_stackex):
        mock_stackex.return_value = {"items": [], "quota_remaining": 999}
        from web.search import search_stackoverflow
        result = await search_stackoverflow("nonexistent")
        assert result["success"] is True
        assert result["data"] == []

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get")
    @patch("web.search.cache_set")
    async def test_cache_hit(self, mock_set, mock_get, mock_stackex):
        mock_get.return_value = "cached results"
        from web.search import search_stackoverflow
        result = await search_stackoverflow("python")
        assert result["data"] == "cached results"
        assert result["meta"]["cached"] is True
        mock_stackex.assert_not_called()

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_min_score_filter(self, mock_set, mock_get, mock_stackex):
        mock_stackex.return_value = {
            "items": [
                {"title": "High", "link": "https://so.com/q/1", "score": 10, "answer_count": 0, "tags": [], "owner": {"display_name": "u1"}},
                {"title": "Low", "link": "https://so.com/q/2", "score": 1, "answer_count": 0, "tags": [], "owner": {"display_name": "u2"}},
            ],
            "quota_remaining": 100,
            "total": 2,
        }
        from web.search import search_stackoverflow
        result = await search_stackoverflow("test", min_score=5)
        assert "High" in result["data"]
        assert "Low" not in result["data"]


class TestGetStackContent:
    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_with_question_id(self, mock_set, mock_get, mock_stackex):
        mock_stackex.side_effect = [
            {"items": [{"title": "Q1", "question_id": 123, "score": 5, "answer_count": 1, "view_count": 100, "tags": ["python"], "link": "https://so.com/q/123", "body": "<p>body</p>"}], "quota_remaining": 100},
            {"items": [{"score": 3, "is_accepted": True, "owner": {"display_name": "u1"}, "body": "<p>answer</p>"}], "quota_remaining": 99},
        ]
        from web.search import get_stack_content
        result = await get_stack_content(question_id=123)
        assert result["success"] is True
        assert "Q1" in result["data"]
        assert "answer" in result["data"]

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_url_parsing(self, mock_set, mock_get, mock_stackex):
        mock_stackex.side_effect = [
            {"items": [{"title": "URL Q", "question_id": 456, "score": 3, "answer_count": 0, "view_count": 50, "tags": [], "link": "https://so.com/q/456", "body": "body"}], "quota_remaining": 100},
            {"items": []},
        ]
        from web.search import get_stack_content
        result = await get_stack_content(url="https://stackoverflow.com/questions/456/some-title")
        assert result["success"] is True
        assert "URL Q" in result["data"]

    @pytest.mark.asyncio
    @patch("web.search.cache_get", return_value=None)
    async def test_no_id_or_url(self, mock_get):
        from web.search import get_stack_content
        result = await get_stack_content()
        assert result["success"] is False
        assert "provide" in result["error"]

    @pytest.mark.asyncio
    @patch("web.search._stackex_get", return_value=None)
    @patch("web.search.cache_get", return_value=None)
    async def test_not_found(self, mock_get, mock_stackex):
        from web.search import get_stack_content
        result = await get_stack_content(question_id=999)
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_answers_excluded(self, mock_set, mock_get, mock_stackex):
        mock_stackex.return_value = {"items": [{"title": "No ans", "question_id": 1, "score": 0, "answer_count": 0, "view_count": 0, "tags": [], "link": "", "body": "body"}], "quota_remaining": 100}
        from web.search import get_stack_content
        result = await get_stack_content(question_id=1, include_answers=False)
        assert "ANSWERS" not in result["data"]

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get")
    @patch("web.search.cache_set")
    async def test_cache_hit(self, mock_set, mock_get, mock_stackex):
        mock_get.return_value = "cached q content"
        from web.search import get_stack_content
        result = await get_stack_content(question_id=1)
        assert result["data"] == "cached q content"
        assert result["meta"]["cached"] is True
        mock_stackex.assert_not_called()

    @pytest.mark.asyncio
    @patch("web.search._stackex_get")
    @patch("web.search.cache_get", return_value=None)
    @patch("web.search.cache_set")
    async def test_min_answer_score(self, mock_set, mock_get, mock_stackex):
        mock_stackex.side_effect = [
            {"items": [{"title": "Q", "question_id": 1, "score": 0, "answer_count": 2, "view_count": 0, "tags": [], "link": "", "body": "body"}], "quota_remaining": 100},
            {"items": [
                {"score": 10, "is_accepted": True, "owner": {"display_name": "u1"}, "body": "high"},
                {"score": 1, "is_accepted": False, "owner": {"display_name": "u2"}, "body": "low"},
            ]},
        ]
        from web.search import get_stack_content
        result = await get_stack_content(question_id=1, min_answer_score=5)
        assert "high" in result["data"]
        assert "low" not in result["data"]


# ==============================================================================
# docs.py
# ==============================================================================

class TestSearchMdn:
    @pytest.mark.asyncio
    @patch("web.docs.cache_get", return_value=None)
    @patch("web.docs.cache_set")
    @patch("web.docs.httpx.AsyncClient")
    async def test_success(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "documents": [{"title": "Array", "summary": "Array docs", "mdn_url": "/en-US/docs/Web/JavaScript/Array"}]
        }
        mock_http.return_value = _mock_http_client(resp)
        from web.docs import search_mdn
        result = await search_mdn("array")
        assert result["success"] is True
        assert "Array" in result["data"]
        assert "developer.mozilla.org" in result["data"]

    @pytest.mark.asyncio
    @patch("web.docs.cache_get", return_value=None)
    @patch("web.docs.cache_set")
    @patch("web.docs.httpx.AsyncClient")
    async def test_url_params(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"documents": []}
        mock_http.return_value = _mock_http_client(resp)
        from web.docs import search_mdn
        await search_mdn("fetch", limit=3, locale="fr")
        call_kwargs = mock_http.return_value.get.call_args[1]
        assert call_kwargs["params"]["q"] == "fetch"
        assert call_kwargs["params"]["locale"] == "fr"

    @pytest.mark.asyncio
    @patch("web.docs.cache_get", return_value=None)
    @patch("web.docs.cache_set")
    @patch("web.docs.httpx.AsyncClient")
    async def test_empty_results(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"documents": []}
        mock_http.return_value = _mock_http_client(resp)
        from web.docs import search_mdn
        result = await search_mdn("zzz_nonexistent")
        assert result["success"] is True
        assert result["data"] == []

    @pytest.mark.asyncio
    @patch("web.docs.cache_get", return_value=None)
    @patch("web.docs.cache_set")
    @patch("web.docs.httpx.AsyncClient")
    async def test_http_error(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 500
        mock_http.return_value = _mock_http_client(resp)
        from web.docs import search_mdn
        result = await search_mdn("test")
        assert result["success"] is False
        assert "500" in result["error"]

    @pytest.mark.asyncio
    @patch("web.docs.cache_get", return_value=None)
    @patch("web.docs.cache_set")
    @patch("web.docs.httpx.AsyncClient")
    async def test_exception_handled(self, mock_http, mock_set, mock_get):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(side_effect=RuntimeError("network failure"))
        mock_http.return_value = client
        from web.docs import search_mdn
        result = await search_mdn("test")
        assert result["success"] is False
        assert "network failure" in result["error"]

    @pytest.mark.asyncio
    @patch("web.docs.cache_get", return_value="cached")
    @patch("web.docs.cache_set")
    @patch("web.docs.httpx.AsyncClient")
    async def test_cache_hit(self, mock_http, mock_set, mock_get):
        from web.docs import search_mdn
        result = await search_mdn("array")
        assert result["data"] == "cached"
        assert result["meta"]["cached"] is True


# ==============================================================================
# registries.py
# ==============================================================================

class TestSearchNpm:
    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_success(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "objects": [{
                "package": {"name": "lodash", "version": "4.17.21", "description": "JS utility",
                            "links": {"npm": "https://npmjs.com/lodash", "repository": "https://github.com/lodash"}},
                "score": {"final": 0.95},
            }]
        }
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_npm
        result = await search_npm("lodash")
        assert result["success"] is True
        assert "lodash@4.17.21" in result["data"]
        assert "0.950" in result["data"]

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_url_params(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"objects": []}
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_npm
        await search_npm("test", limit=3)
        call_kwargs = mock_http.return_value.get.call_args[1]
        assert call_kwargs["params"]["text"] == "test"

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_empty_results(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"objects": []}
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_npm
        result = await search_npm("nonexistent")
        assert result["success"] is True
        assert result["data"] == []

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_http_error(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 500
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_npm
        result = await search_npm("test")
        assert result["success"] is False

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_repo_link_included(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "objects": [{
                "package": {"name": "pkg", "version": "1.0.0", "description": "",
                            "links": {"npm": "https://npmjs.com/pkg", "repository": "https://github.com/pkg"}},
                "score": {"final": 0.8},
            }]
        }
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_npm
        result = await search_npm("pkg")
        assert "Repo:" in result["data"]


class TestSearchPypi:
    """search_pypi has 3-tier search with multiple HTTP calls."""

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_exact_match(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "info": {"name": "requests", "version": "2.31.0", "summary": "HTTP lib",
                     "author": "Kenneth", "license": "Apache", "home_page": "https://requests.org",
                     "requires_python": ">=3.7", "project_urls": {}},
        }
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_pypi
        result = await search_pypi("requests")
        assert result["success"] is True
        assert "requests==2.31.0" in result["data"]
        assert result["meta"]["source"] == "exact"

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_prefix_fallback(self, mock_http, mock_set, mock_get):
        resp_exact = MagicMock()
        resp_exact.status_code = 404

        resp_prefix = MagicMock()
        resp_prefix.status_code = 200
        resp_prefix.text = '<a href="/simple/flask/1.0.0/">flask-1.0.0</a>'

        c1 = _mock_http_client(resp_exact)
        c2 = _mock_http_client(resp_prefix)
        mock_http.side_effect = [c1, c2]

        from web.registries import search_pypi
        result = await search_pypi("flask")
        assert result["success"] is True
        assert "release files" in result["data"]
        assert result["meta"]["source"] == "prefix"

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_broad_prefix_fallback(self, mock_http, mock_set, mock_get):
        def _json_resp(data, status=200):
            r = MagicMock()
            r.status_code = status
            r.json.return_value = data
            return r

        def _text_resp(text, status=200):
            r = MagicMock()
            r.status_code = status
            r.text = text
            return r

        clients = [
            _mock_http_client(_json_resp({"error": "not found"}, 404)),
            _mock_http_client(_text_resp("", 404)),
            _mock_http_client(_text_resp(
                '<a href="/simple/foo/">foo</a><a href="/simple/foobar/">foobar</a>')),
            _mock_http_client(_json_resp({
                "info": {"name": "foo", "version": "1.0", "summary": "Foo pkg"}})),
            _mock_http_client(_json_resp({
                "info": {"name": "foobar", "version": "2.0", "summary": "Foobar pkg"}})),
        ]
        mock_http.side_effect = clients

        from web.registries import search_pypi
        result = await search_pypi("foo")
        assert result["success"] is True
        assert result["meta"]["source"] == "broad_prefix"

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_no_results(self, mock_http, mock_set, mock_get):
        clients = [
            _mock_http_client(MagicMock(status_code=404)),
            _mock_http_client(MagicMock(status_code=404)),
            _mock_http_client(MagicMock(
                status_code=200, text='<a href="/simple/zzz/">zzz</a><a href="/simple/aaa/">aaa</a>')),
        ]
        mock_http.side_effect = clients
        from web.registries import search_pypi
        result = await search_pypi("qqq")
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value="cached")
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_cache_hit(self, mock_http, mock_set, mock_get):
        from web.registries import search_pypi
        result = await search_pypi("requests")
        assert result["success"] is True
        assert result["meta"]["cached"] is True


class TestSearchCrates:
    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_success(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "crates": [{"name": "serde", "max_version": "1.0.200", "description": "Serialization framework",
                        "downloads": 100_000_000, "documentation": "https://docs.rs/serde"}]
        }
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_crates
        result = await search_crates("serde")
        assert result["success"] is True
        assert "serde v1.0.200" in result["data"]
        assert "100,000,000" in result["data"]

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_http_error(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 403
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_crates
        result = await search_crates("test")
        assert result["success"] is False
        assert "403" in result["error"]

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_empty_results(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"crates": []}
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_crates
        result = await search_crates("nonexistent")
        assert result["success"] is True
        assert result["data"] == []

    @pytest.mark.asyncio
    @patch("web.registries.cache_get", return_value=None)
    @patch("web.registries.cache_set")
    @patch("web.registries.httpx.AsyncClient")
    async def test_url_construction(self, mock_http, mock_set, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"crates": []}
        mock_http.return_value = _mock_http_client(resp)
        from web.registries import search_crates
        await search_crates("tokio", limit=3)
        call_args = mock_http.return_value.get.call_args
        assert "crates.io/api/v1/crates" in call_args[0][0]
        assert call_args[1]["params"]["q"] == "tokio"


# ==============================================================================
# mcp_web.py — all 10 tools
# ==============================================================================

class TestMcpWebTools:
    """Verify each MCP tool calls the right impl function and returns JSON."""

    @pytest.mark.asyncio
    @patch("mcp_web._fetch_url_impl", new_callable=AsyncMock)
    async def test_fetch_url(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "content", "tool": "fetch_url"}
        from mcp_web import fetch_url
        result = await fetch_url("https://example.com", max_length=100, raw=True)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("https://example.com", 100, 0, True)

    @pytest.mark.asyncio
    @patch("mcp_web._fetch_url_impl", new_callable=AsyncMock)
    async def test_fetch_url_defaults(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "", "tool": "fetch_url"}
        from mcp_web import fetch_url
        await fetch_url("https://example.com")
        mock_impl.assert_called_once_with("https://example.com", 5000, 0, False)

    @pytest.mark.asyncio
    @patch("mcp_web._search_web_impl", new_callable=AsyncMock)
    async def test_search_web(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "results", "tool": "search_web"}
        from mcp_web import search_web
        result = await search_web("python", max_results=3)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("python", 3)

    @pytest.mark.asyncio
    @patch("mcp_web._search_so_impl", new_callable=AsyncMock)
    async def test_search_stackoverflow(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "so results", "tool": "search_stackoverflow"}
        from mcp_web import search_stackoverflow
        result = await search_stackoverflow("query", max_results=5, tags="python", min_score=1, sort="votes")
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("query", 5, "python", 1, "votes")

    @pytest.mark.asyncio
    @patch("mcp_web._get_sc_impl", new_callable=AsyncMock)
    async def test_get_stack_content(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "q content", "tool": "get_stack_content"}
        from mcp_web import get_stack_content
        result = await get_stack_content(question_id=123, url="", include_answers=True, max_answers=5, min_answer_score=0)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with(123, "", True, 5, 0)

    @pytest.mark.asyncio
    @patch("mcp_web._search_npm_impl", new_callable=AsyncMock)
    async def test_search_npm(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "npm results", "tool": "search_npm"}
        from mcp_web import search_npm
        result = await search_npm("lodash", limit=10, detail=True)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("lodash", 10, True)

    @pytest.mark.asyncio
    @patch("mcp_web._search_pypi_impl", new_callable=AsyncMock)
    async def test_search_pypi(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "pypi results", "tool": "search_pypi"}
        from mcp_web import search_pypi
        result = await search_pypi("requests", limit=3)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("requests", 3)

    @pytest.mark.asyncio
    @patch("mcp_web._search_crates_impl", new_callable=AsyncMock)
    async def test_search_crates(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "crates results", "tool": "search_crates"}
        from mcp_web import search_crates
        result = await search_crates("serde", limit=5)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("serde", 5)

    @pytest.mark.asyncio
    @patch("mcp_web._search_rtd_impl", new_callable=AsyncMock)
    async def test_search_readthedocs(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "rtd results", "tool": "search_readthedocs"}
        from mcp_web import search_readthedocs
        result = await search_readthedocs("django", limit=5)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("django", 5)

    @pytest.mark.asyncio
    @patch("mcp_web._search_mdn_impl", new_callable=AsyncMock)
    async def test_search_mdn(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "mdn results", "tool": "search_mdn"}
        from mcp_web import search_mdn
        result = await search_mdn("array", limit=3, locale="en-US")
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("array", 3, "en-US")

    @pytest.mark.asyncio
    @patch("mcp_web._search_devdocs_impl", new_callable=AsyncMock)
    async def test_search_devdocs(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "devdocs results", "tool": "search_devdocs"}
        from mcp_web import search_devdocs
        result = await search_devdocs(query="python", doc_filter="python", limit=5)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_impl.assert_called_once_with("python", "python", 5)

    @pytest.mark.asyncio
    @patch("mcp_web._search_devdocs_impl", new_callable=AsyncMock)
    async def test_search_devdocs_defaults(self, mock_impl):
        mock_impl.return_value = {"success": True, "data": "", "tool": "search_devdocs"}
        from mcp_web import search_devdocs
        await search_devdocs()
        mock_impl.assert_called_once_with("", "", 5)
