"""
mcp_web.py — MCPKU Developer Research Engine (entry point)

Thin layer: imports implementations from web/ package, registers MCP tools,
and wraps structured dict responses into JSON strings for MCP protocol.

Architecture:
  mcp_web.py  (entry point — registers MCP tools, formats JSON output)
      │
      └── web/  (package — pure implementation, httpx-native, structured dicts)
           ├── cache.py       # Redis cache wrappers
           ├── parsers.py     # HTML cleanup, JSON response builders
           ├── fetch.py       # fetch_url
           ├── search.py      # search_web, search_stackoverflow, get_stack_content
           ├── docs.py        # search_mdn, search_devdocs, search_readthedocs
           └── registries.py  # search_npm, search_pypi, search_crates
"""

import json
import os

from mcp.server.fastmcp import FastMCP

# Import pure implementations from web/ package
from web.fetch import fetch_url as _fetch_url_impl
from web.search import search_web as _search_web_impl
from web.search import search_stackoverflow as _search_so_impl
from web.search import get_stack_content as _get_sc_impl
from web.docs import search_mdn as _search_mdn_impl
from web.docs import search_devdocs as _search_devdocs_impl
from web.docs import search_readthedocs as _search_rtd_impl
from web.registries import search_npm as _search_npm_impl
from web.registries import search_pypi as _search_pypi_impl
from web.registries import search_crates as _search_crates_impl
from web.parsers import html_to_text as _html_to_text, json_ok, json_error

_FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

mcp = FastMCP("web-tools", instructions="""
Web fetch and search tools for real-time information. fetch_url extracts
content as clean text/markdown. search_web uses DuckDuckGo (free, no key)
with Firecrawl fallback if configured.

Stack Exchange tools (search_stackoverflow, get_stack_content) use the
official Stack Exchange API with 10,000 requests/day quota.

Results are cached in Redis for 1 hour (fetch_url) or 30 minutes (search_web)
to avoid redundant API calls. Use ?nocache=true in URL to bypass cache.
""")


def _wrap(fn):
    """Wrap impl function: call it, return JSON string."""
    async def wrapper(*args, **kwargs):
        result = await fn(*args, **kwargs)
        return json.dumps(result, ensure_ascii=False)
    return wrapper


# ── Tool Registrations ──────────────────────────────────────────────────────

@mcp.tool(name="fetch_url",
          description="Fetch content dari URL web. Gunakan start_index untuk membaca halaman panjang per bagian.")
async def fetch_url(url: str, max_length: int = 5000, start_index: int = 0, raw: bool = False) -> str:
    result = await _fetch_url_impl(url, max_length, start_index, raw)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_web",
          description="Cari informasi real-time di web. Default DuckDuckGo (free, no API key), fallback Firecrawl.")
async def search_web(query: str, max_results: int = 5) -> str:
    result = await _search_web_impl(query, max_results)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_stackoverflow",
          description="Cari pertanyaan di Stack Overflow via API resmi. Gunakan filter tag, score minimal, atau kata kunci spesifik untuk hasil lebih akurat.")
async def search_stackoverflow(query: str, max_results: int = 5, tags: str = "", min_score: int = 0, sort: str = "relevance") -> str:
    result = await _search_so_impl(query, max_results, tags, min_score, sort)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="get_stack_content",
          description="Ambil detail pertanyaan + jawaban dari Stack Exchange berdasarkan ID. Bisa juga ambil langsung dari URL Stack Overflow (parse otomatis ID-nya).")
async def get_stack_content(question_id: int | str = "", url: str = "", include_answers: bool = True, max_answers: int = 3, min_answer_score: int = 0) -> str:
    result = await _get_sc_impl(question_id, url, include_answers, max_answers, min_answer_score)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_npm",
          description="Cari package di npm registry. Returns nama, versi, deskripsi, link.")
async def search_npm(query: str, limit: int = 5, detail: bool = False) -> str:
    result = await _search_npm_impl(query, limit, detail)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_pypi",
          description="Cari package Python di PyPI via JSON API. Cari by nama package (exact atau mirip). Untuk search keyword gunakan search_web() sebagai alternatif.")
async def search_pypi(query: str, limit: int = 5) -> str:
    result = await _search_pypi_impl(query, limit)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_crates",
          description="Cari Rust crate di crates.io. Returns nama, versi, deskripsi, downloads.")
async def search_crates(query: str, limit: int = 5) -> str:
    result = await _search_crates_impl(query, limit)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_readthedocs",
          description="Cari dokumentasi library Python di ReadTheDocs.")
async def search_readthedocs(query: str, limit: int = 5) -> str:
    result = await _search_rtd_impl(query, limit)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_mdn",
          description="Cari dokumentasi web di MDN (Mozilla Developer Network). Returns title, summary, link.")
async def search_mdn(query: str, limit: int = 5, locale: str = "en-US") -> str:
    result = await _search_mdn_impl(query, limit, locale)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(name="search_devdocs",
          description="Cari dokumentasi API di DevDocs.io. List doc sets yang tersedia, atau cari dengan query + filter by doc set (python, javascript, rust, dll).")
async def search_devdocs(query: str = "", doc_filter: str = "", limit: int = 5) -> str:
    result = await _search_devdocs_impl(query, doc_filter, limit)
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
