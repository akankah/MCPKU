"""Documentation search: MDN, DevDocs, ReadTheDocs."""

from urllib.parse import quote_plus

import httpx

from web.cache import get as cache_get, set as cache_set
from web.parsers import json_ok, json_error
from web.search import search_web

_TIMEOUT = httpx.Timeout(10.0)


async def search_mdn(query: str, limit: int = 5, locale: str = "en-US") -> dict:
    """Search MDN Web Docs via official API."""
    cache_key = f"mcp:web:mdn:search:{query}:{limit}:{locale}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_mdn", cached, {"cached": True})

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://developer.mozilla.org/api/v1/search",
                params={"q": query, "locale": locale},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code != 200:
                return json_error("search_mdn", f"HTTP {r.status_code}")
            data = r.json()
            docs = data.get("documents", [])
            if not docs:
                return json_ok("search_mdn", [], {"total": 0})

            out = []
            for i, doc in enumerate(docs[:limit], 1):
                title = doc.get("title", "")
                summary = doc.get("summary", "") or ""
                mdn_url = doc.get("mdn_url", "")
                full_url = f"https://developer.mozilla.org{mdn_url}" if mdn_url else ""
                out.append(f"{i}. {title}\n   {summary[:200]}\n   {full_url}")

            result = "\n\n".join(out)
            cache_set(cache_key, result, ttl=3600)
            return json_ok("search_mdn", result, {"total": len(docs)})
        except Exception as e:
            return json_error("search_mdn", str(e))


async def search_devdocs(query: str = "", doc_filter: str = "", limit: int = 5) -> dict:
    """Search DevDocs doc sets."""
    cache_key = f"mcp:web:devdocs:search:{query}:{doc_filter}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_devdocs", cached, {"cached": True})

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://devdocs.io/docs.json",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code != 200:
                return json_error("search_devdocs", f"HTTP {r.status_code}")
            all_docs = r.json()
        except Exception as e:
            return json_error("search_devdocs", str(e))

    if doc_filter:
        matching = [d for d in all_docs
                    if doc_filter.lower() in d.get("slug", "").lower()
                    or doc_filter.lower() in d.get("name", "").lower()]
    else:
        matching = all_docs

    if not matching:
        return json_ok("search_devdocs", [], {"total": 0, "filter": doc_filter})

    if not query:
        out = [f"DevDocs doc sets matching '{doc_filter or 'all'}':\n"]
        for d in matching[:limit]:
            name = d.get("name", "")
            slug = d.get("slug", "")
            version = d.get("version", "") or d.get("release", "")
            links = d.get("links", {})
            home = links.get("home", "")
            out.append(f"  [{slug}] {name} {version}")
            if home:
                out.append(f"    {home}")
        result = "\n".join(out)
    else:
        out = [f"DevDocs search results for '{query}' in '{doc_filter or 'all'}':\n"]
        for d in matching[:limit]:
            slug = d.get("slug", "")
            name = d.get("name", "")
            search_url = f"https://devdocs.io/#q={quote_plus(query)}"
            doc_url = f"https://devdocs.io/{slug}/"
            out.append(f"  [{name} ({slug})]")
            out.append(f"    Search: {search_url}")
            out.append(f"    Docs:   {doc_url}")
        out.append("\n(Catatan: DevDocs search bersifat client-side — buka link di browser untuk hasil interaktif.)")
        result = "\n".join(out)

    cache_set(cache_key, result, ttl=1800)
    return json_ok("search_devdocs", result, {"total": len(matching)})


async def search_readthedocs(query: str, limit: int = 5) -> dict:
    """Search ReadTheDocs via site-restricted web search."""
    result = await search_web(f"site:readthedocs.io {query}", max_results=limit)
    return result
