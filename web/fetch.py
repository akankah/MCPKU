"""URL fetch with httpx async-native HTTP client."""

import httpx

from web.cache import get as cache_get, set as cache_set
from web.parsers import html_to_text, json_ok, json_error

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_TIMEOUT = httpx.Timeout(15.0)


async def fetch_url(
    url: str,
    max_length: int = 5000,
    start_index: int = 0,
    raw: bool = False,
) -> dict:
    """Fetch URL content, return structured dict."""
    nocache = "?nocache=true" in url.lower() or "&nocache=true" in url.lower()
    cache_key = f"mcp:web:fetch:{url}:{max_length}:{start_index}:{raw}"

    if not nocache:
        cached = cache_get(cache_key)
        if cached is not None:
            return json_ok("fetch_url", cached, {"source": url, "cached": True})

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=_HEADERS)
            r.raise_for_status()
            text = r.text if raw else html_to_text(r.text)
            if start_index > 0:
                text = text[start_index:]
            if len(text) > max_length:
                text = text[:max_length] + "\n\n[...truncated, use start_index to continue]"

            if not nocache:
                cache_set(cache_key, text, ttl=3600)

            return json_ok("fetch_url", text, {"source": url, "cached": False})
        except httpx.TimeoutException:
            return json_error("fetch_url", "timeout", f"fetching {url}")
        except Exception as e:
            return json_error("fetch_url", str(e), f"fetching {url}")
