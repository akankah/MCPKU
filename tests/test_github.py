"""Tests for mcp_github.py — mocked HTTP layer.

These tests mock requests.get/post/patch/put/delete to avoid
requiring a real GITHUB_API_KEY or network access.
"""

import json
import sys
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, r"E:\MCPKU")

from mcp_github import (
    _headers,
    _api,
    _get,
    _post,
    _patch,
    _put,
    _delete,
    _format_repo,
    search_repos,
    get_repo,
    list_issues,
)


class TestHeaders:
    @patch("mcp_github.GITHUB_TOKEN", "test_token")
    def test_includes_auth(self):
        h = _headers()
        assert h["Authorization"] == "Bearer test_token"
        assert h["User-Agent"] == "mcp-github-server"
        assert "Accept" in h


class TestApi:
    @patch("mcp_github.requests.request")
    def test_get_success(self, mock_req):
        mock_req.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}, raise_for_status=lambda: None,
        )
        result = _api("get", "/repos/test")
        assert result == {"id": 1}

    @patch("mcp_github.requests.request")
    def test_post_sends_json(self, mock_req):
        mock_req.return_value = MagicMock(
            status_code=201, json=lambda: {"id": 2}, raise_for_status=lambda: None,
        )
        result = _api("post", "/repos", data={"name": "new"})
        assert result == {"id": 2}
        assert mock_req.call_args[1]["json"] == {"name": "new"}

    @patch("mcp_github.requests.request")
    def test_delete_204_returns_deleted(self, mock_req):
        mock_req.return_value = MagicMock(
            status_code=204, raise_for_status=lambda: None,
        )
        result = _api("delete", "/repos/test")
        assert result == {"deleted": True}

    @patch("mcp_github.requests.request")
    def test_http_error_returns_error_dict(self, mock_req):
        resp = MagicMock(status_code=404)
        resp.text = "Not Found"
        from requests.exceptions import HTTPError
        mock_req.side_effect = HTTPError(response=resp)
        result = _api("get", "/bad")
        assert "error" in result
        assert "404" in result["error"]

    @patch("mcp_github.requests.request")
    def test_network_error_returns_error_dict(self, mock_req):
        mock_req.side_effect = ConnectionError("down")
        result = _api("get", "/bad")
        assert "error" in result


class TestGet:
    @patch("mcp_github._api")
    def test_get_delegates_to_api(self, mock_api):
        mock_api.return_value = {"id": 1}
        result = _get("/repos/test", params={"q": "test"})
        assert result == {"id": 1}
        mock_api.assert_called_with("get", "/repos/test", params={"q": "test"})


class TestPost:
    @patch("mcp_github._api")
    def test_post_delegates_to_api(self, mock_api):
        mock_api.return_value = {"id": 2}
        result = _post("/repos", data={"name": "new"})
        assert result == {"id": 2}
        mock_api.assert_called_with("post", "/repos", data={"name": "new"})


class TestPut:
    @patch("mcp_github._api")
    def test_put_delegates_to_api(self, mock_api):
        mock_api.return_value = {"updated": True}
        result = _put("/repos/test", data={"name": "new"})
        assert result == {"updated": True}
        mock_api.assert_called_with("put", "/repos/test", data={"name": "new"})


class TestPatch:
    @patch("mcp_github._api")
    def test_patch_delegates_to_api(self, mock_api):
        mock_api.return_value = {"patched": True}
        result = _patch("/repos/test", data={"name": "new"})
        assert result == {"patched": True}
        mock_api.assert_called_with("patch", "/repos/test", data={"name": "new"})


class TestDelete:
    @patch("mcp_github._api")
    def test_delete_delegates_to_api(self, mock_api):
        mock_api.return_value = {"deleted": True}
        result = _delete("/repos/test")
        assert result == {"deleted": True}
        mock_api.assert_called_with("delete", "/repos/test")


class TestFormatRepo:
    def test_basic_fields(self):
        r = {
            "full_name": "owner/repo",
            "description": "A test repo",
            "stargazers_count": 42,
            "forks_count": 7,
            "language": "Python",
            "html_url": "https://github.com/owner/repo",
            "topics": ["python", "cli"],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-06-01T00:00:00Z",
        }
        result = _format_repo(r)
        assert "owner/repo" in result
        assert "42" in result
        assert "Python" in result
        assert "python, cli" in result

    def test_missing_fields(self):
        result = _format_repo({"full_name": "x/y"})
        assert "x/y" in result


@pytest.mark.asyncio
@patch("mcp_github._get")
async def test_search_repos_success(mock_get):
    mock_get.return_value = {
        "total_count": 1,
        "items": [{
            "full_name": "test/repo",
            "description": "desc",
            "stargazers_count": 5,
            "forks_count": 1,
            "language": "Python",
            "html_url": "https://github.com/test/repo",
            "topics": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-06-01T00:00:00Z",
        }]
    }
    result = await search_repos("test", max_results=5)
    assert "test/repo" in result
    assert "Found 1" in result


@pytest.mark.asyncio
@patch("mcp_github._get")
async def test_search_repos_error(mock_get):
    mock_get.return_value = {"error": "HTTP 403: rate limited"}
    result = await search_repos("test")
    assert "error" in result
    assert "rate limited" in result


@pytest.mark.asyncio
@patch("mcp_github._get")
async def test_get_repo_success(mock_get):
    mock_get.return_value = {
        "full_name": "owner/repo",
        "description": "A repo",
        "stargazers_count": 100,
        "forks_count": 20,
        "language": "Go",
        "html_url": "https://github.com/owner/repo",
        "topics": ["go"],
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2024-06-01T00:00:00Z",
    }
    result = await get_repo("owner/repo")
    assert "owner/repo" in result
    assert "Go" in result


@pytest.mark.asyncio
@patch("mcp_github._get")
async def test_list_issues_empty(mock_get):
    mock_get.return_value = []
    result = await list_issues("owner/repo", max_results=5)
    assert "no issues" in result.lower() or "(no results)" in result
