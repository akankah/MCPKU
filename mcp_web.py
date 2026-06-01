import os, re, html, json
from urllib.parse import quote_plus, urlencode
from mcp.server.fastmcp import FastMCP
import requests
from mcp_cache import cache_get, cache_set

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
_DDG_ENABLED = os.environ.get("DISABLE_DUCKDUCKGO", "0") != "1"

mcp = FastMCP("web-tools", instructions="""
Web fetch and search tools for real-time information. fetch_url extracts
content as clean text/markdown. search_web uses DuckDuckGo (free, no key)
with Firecrawl fallback if configured.

Results are cached in Redis for 1 hour (fetch_url) or 30 minutes (search_web)
to avoid redundant API calls. Use ?nocache=true in URL to bypass cache.
""")

def _html_to_text(html_content: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(div|h[1-6]|li|tr|pre|blockquote)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>', r'[\1] ', text, flags=re.IGNORECASE)
    text = re.sub(r'<img\s[^>]*alt="([^"]*)"[^>]*>', r' \1 ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()

@mcp.tool(
    name="fetch_url",
    description="Fetch content dari URL web. Gunakan start_index untuk membaca halaman panjang per bagian."
)
async def fetch_url(url: str, max_length: int = 5000, start_index: int = 0, raw: bool = False) -> str:
    nocache = "?nocache=true" in url.lower() or "&nocache=true" in url.lower()
    if not nocache:
        cache_key = f"mcp:web:fetch:{url}:{max_length}:{start_index}:{raw}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        text = r.text if raw else _html_to_text(r.text)
        if start_index > 0:
            text = text[start_index:]
        if len(text) > max_length:
            text = text[:max_length] + "\n\n[...truncated, use start_index to continue]"

        if not nocache:
            cache_set(cache_key, text, ttl=3600)

        return text if text else "(empty page)"
    except requests.exceptions.Timeout:
        return f"(timeout fetching {url})"
    except Exception as e:
        return f"(error fetching {url}: {e})"

def _scrape_ddg(query: str, max_results: int = 5) -> str | None:
    """Scrape DuckDuckGo lite HTML directly (free, no API key needed)."""
    if not _DDG_ENABLED:
        return None
    try:
        r = requests.post("https://lite.duckduckgo.com/lite/", data={"q": query}, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }, timeout=10)
        r.raise_for_status()

        # Each result = 3 consecutive <tr> rows: title, snippet, domain
        links = re.findall(
            r'<a rel="nofollow" href="([^"]+)"[^>]*class=\'result-link\'[^>]*>(.+?)</a>',
            r.text, re.DOTALL
        )
        snippets = re.findall(
            r"<td class='result-snippet'>(.+?)</td>",
            r.text, re.DOTALL
        )

        out = []
        for i, (href, title_html) in enumerate(links[:max_results]):
            title = html.unescape(re.sub(r'<[^>]+>', '', title_html)).strip()
            snippet = html.unescape(re.sub(r'<[^>]+>', '', snippets[i])).strip() if i < len(snippets) else ""
            out.append(f"{i+1}. {title}\n   {snippet}\n   {href}")

        return "\n\n".join(out) if out else None
    except Exception:
        return None


@mcp.tool(
    name="search_web",
    description="Cari informasi real-time di web. Default DuckDuckGo (free, no API key), fallback Firecrawl."
)
async def search_web(query: str, max_results: int = 5) -> str:
    cache_key = f"mcp:web:search:{query}:{max_results}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # DuckDuckGo (free, zero config)
    import asyncio
    ddg = await asyncio.to_thread(_scrape_ddg, query, max_results)
    if ddg is not None:
        cache_set(cache_key, ddg, ttl=1800)
        return ddg

    # Fallback: Firecrawl
    if FIRECRAWL_API_KEY:
        try:
            r = requests.post(
                "https://api.firecrawl.dev/v1/search",
                json={"query": query},
                headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"},
                timeout=15,
            )
            if r.status_code != 200:
                return f"(search failed: HTTP {r.status_code})"
            data = r.json()
            results = data.get("data", [])
            if not results:
                return "(no results)"
            out = []
            for i, res in enumerate(results[:max_results], 1):
                title = res.get("title", "")
                snippet = res.get("snippet", "") or res.get("description", "")
                link = res.get("url", "")
                out.append(f"{i}. {title}\n   {snippet}\n   {link}")
            text = "\n\n".join(out)
            cache_set(cache_key, text, ttl=1800)
            return text
        except Exception as e:
            return f"(firecrawl search failed: {e})"

    return "(no search available — install duckduckgo_search or set FIRECRAWL_API_KEY)"

if __name__ == "__main__":
    mcp.run(transport="stdio")
