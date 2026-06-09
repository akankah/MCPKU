"""Tests for mcp_browser.py — mocked Playwright layer."""

import sys
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

sys.path.insert(0, r"E:\MCPKU")

from mcp_browser import browser_fetch, screenshot


@pytest.mark.asyncio
@patch("mcp_browser._new_page", new_callable=AsyncMock)
async def test_browser_fetch_adds_https(mock_new_page):
    mock_page = AsyncMock()
    mock_page.inner_text.return_value = "Hello world"
    mock_ctx = AsyncMock()
    mock_new_page.return_value = (mock_page, mock_ctx)

    result = await browser_fetch("example.com")
    assert "Hello world" in result
    # Verify goto was called with https://
    call_url = mock_page.goto.call_args[0][0]
    assert call_url.startswith("https://")


@pytest.mark.asyncio
@patch("mcp_browser._new_page", new_callable=AsyncMock)
async def test_browser_fetch_empty_text(mock_new_page):
    mock_page = AsyncMock()
    mock_page.inner_text.return_value = ""
    mock_ctx = AsyncMock()
    mock_new_page.return_value = (mock_page, mock_ctx)

    result = await browser_fetch("https://example.com")
    assert "no text content" in result


@pytest.mark.asyncio
@patch("mcp_browser._new_page", new_callable=AsyncMock)
async def test_browser_fetch_truncates_long(mock_new_page):
    mock_page = AsyncMock()
    mock_page.inner_text.return_value = "A" * 5000
    mock_ctx = AsyncMock()
    mock_new_page.return_value = (mock_page, mock_ctx)

    result = await browser_fetch("https://example.com", max_chars=100)
    assert len(result) < 200
    assert "truncated" in result


@pytest.mark.asyncio
@patch("mcp_browser._new_page", new_callable=AsyncMock)
async def test_browser_fetch_error_returns_message(mock_new_page):
    mock_new_page.side_effect = RuntimeError("connection refused")
    result = await browser_fetch("https://example.com")
    assert "browser error" in result
    assert "connection refused" in result


@pytest.mark.asyncio
@patch("mcp_browser._new_page", new_callable=AsyncMock)
async def test_screenshot_adds_https(mock_new_page):
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"pngdata"
    mock_ctx = AsyncMock()
    mock_new_page.return_value = (mock_page, mock_ctx)

    result = await screenshot("example.com")
    assert "data:image/png;base64," in result

    call_url = mock_page.goto.call_args[0][0]
    assert call_url.startswith("https://")


@pytest.mark.asyncio
@patch("mcp_browser._new_page", new_callable=AsyncMock)
async def test_screenshot_error_returns_message(mock_new_page):
    mock_new_page.side_effect = ValueError("bad url")
    result = await screenshot("https://example.com")
    assert "screenshot error" in result
    assert "bad url" in result
