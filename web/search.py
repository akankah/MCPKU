"""Search engines: DuckDuckGo, Firecrawl, Stack Overflow."""

import asyncio
import html as html_mod
import re

import httpx

from web.cache import get as cache_get, set as cache_set
from web.parsers import json_ok, json_error

_DDG_ENABLED = __import__("os").environ.get("DISABLE_DUCKDUCKGO", "0") != "1"
_FIRECRAWL_KEY = __import__("os").environ.get("FIRECRAWL_API_KEY", "")
_STACKEX_KEY = __import__("os").environ.get("STACKEX_API_KEY", "")
_STACKEX_BASE = "https://api.stackexchange.com/2.3"
_TIMEOUT = httpx.Timeout(15.0)


# ── DuckDuckGo ──────────────────────────────────────────────────────────────

async def _scrape_ddg(query: str, max_results: int = 5) -> str | None:
    """Scrape DuckDuckGo lite — free, no API key."""
    if not _DDG_ENABLED:
        return None
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            r = await client.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            r.raise_for_status()
            links = re.findall(
                r'<a rel="nofollow" href="([^"]+)"[^>]*class=\'result-link\'[^>]*>(.+?)</a>',
                r.text, re.DOTALL,
            )
            snippets = re.findall(
                r"<td class='result-snippet'>(.+?)</td>",
                r.text, re.DOTALL,
            )
            out = []
            for i, (href, title_html) in enumerate(links[:max_results]):
                title = html_mod.unescape(re.sub(r'<[^>]+>', '', title_html)).strip()
                snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', snippets[i])).strip() if i < len(snippets) else ""
                out.append(f"{i+1}. {title}\n   {snippet}\n   {href}")
            return "\n\n".join(out) if out else None
        except Exception:
            return None


async def _firecrawl_search(query: str, max_results: int = 5) -> str | None:
    """Firecrawl search as DDG fallback."""
    if not _FIRECRAWL_KEY:
        return None
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.post(
                "https://api.firecrawl.dev/v1/search",
                json={"query": query},
                headers={"Authorization": f"Bearer {_FIRECRAWL_KEY}", "Content-Type": "application/json"},
            )
            if r.status_code != 200:
                return None
            data = r.json()
            results = data.get("data", [])
            if not results:
                return None
            out = []
            for i, res in enumerate(results[:max_results], 1):
                title = res.get("title", "")
                snippet = res.get("snippet", "") or res.get("description", "")
                link = res.get("url", "")
                out.append(f"{i}. {title}\n   {snippet}\n   {link}")
            return "\n\n".join(out) if out else None
        except Exception:
            return None


async def search_web(query: str, max_results: int = 5) -> dict:
    """Web search via DDG, fallback Firecrawl. Returns structured dict."""
    cache_key = f"mcp:web:search:{query}:{max_results}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_web", cached, {"source": "cache", "cached": True})

    ddg_result = await _scrape_ddg(query, max_results)
    if ddg_result is not None:
        cache_set(cache_key, ddg_result, ttl=1800)
        return json_ok("search_web", ddg_result, {"source": "duckduckgo"})

    fc_result = await _firecrawl_search(query, max_results)
    if fc_result is not None:
        cache_set(cache_key, fc_result, ttl=1800)
        return json_ok("search_web", fc_result, {"source": "firecrawl"})

    return json_error("search_web", "no search available",
                      "Install duckduckgo_search or set FIRECRAWL_API_KEY")


# ── Stack Overflow / Stack Exchange ─────────────────────────────────────────

async def _stackex_get(path: str, params: dict) -> dict | None:
    params.setdefault("key", _STACKEX_KEY)
    params.setdefault("site", "stackoverflow")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.get(f"{_STACKEX_BASE}{path}", params=params)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None


def _format_question(item: dict) -> str:
    title = item.get("title", "(no title)")
    link = item.get("link", "")
    score = item.get("score", 0)
    answers = item.get("answer_count", 0)
    accepted = " ✓" if item.get("accepted_answer_id") else ""
    tags = ", ".join(item.get("tags", []))
    owner = item.get("owner", {}).get("display_name", "anonymous")
    return (
        f"[{score} votes | {answers} answers{accepted}] {title}\n"
        f"    tags: {tags} | by {owner}\n"
        f"    {link}"
    )


def _format_answer(item: dict) -> str:
    score = item.get("score", 0)
    accepted = " ✓ ACCEPTED" if item.get("is_accepted") else ""
    owner = item.get("owner", {}).get("display_name", "anonymous")
    body = re.sub(r"<[^>]+>", "", item.get("body", "") or "")
    body = html_mod.unescape(body)[:2000]
    return f"[{score} votes{accepted}] by {owner}\n{body}\n"


async def search_stackoverflow(
    query: str,
    max_results: int = 5,
    tags: str = "",
    min_score: int = 0,
    sort: str = "relevance",
) -> dict:
    """Search Stack Overflow via official API."""
    cache_key = f"mcp:web:so:search:{query}:{tags}:{min_score}:{sort}:{max_results}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_stackoverflow", cached, {"cached": True})

    params = {
        "q": query, "sort": sort, "order": "desc",
        "pagesize": min(max_results, 20), "filter": "withbody",
        "site": "stackoverflow",
    }
    if _STACKEX_KEY:
        params["key"] = _STACKEX_KEY
    if tags:
        params["tagged"] = tags

    data = await _stackex_get("/search/advanced", params)
    if not data:
        return json_error("search_stackoverflow", "API error or no response")

    items = data.get("items", [])
    if not items:
        return json_ok("search_stackoverflow", [], {"quota_remaining": data.get("quota_remaining")})

    if min_score > 0:
        items = [i for i in items if i.get("score", 0) >= min_score]

    out_parts = []
    for i, item in enumerate(items[:max_results], 1):
        out_parts.append(f"{i}. {_format_question(item)}")

    result = "\n\n".join(out_parts)
    meta = {"quota_remaining": data.get("quota_remaining"), "total": data.get("total", len(items))}
    cache_set(cache_key, result, ttl=3600)
    return json_ok("search_stackoverflow", result, meta)


async def get_stack_content(
    question_id: int | str = "",
    url: str = "",
    include_answers: bool = True,
    max_answers: int = 3,
    min_answer_score: int = 0,
) -> dict:
    """Get question + answers from Stack Exchange."""
    if url and not question_id:
        m = re.search(r"(?:questions|q)/(\d+)", url)
        question_id = int(m.group(1)) if m else 0
    if not question_id:
        return json_error("get_stack_content", "provide question_id or url")

    cache_key = f"mcp:web:so:get:{question_id}:{include_answers}:{max_answers}:{min_answer_score}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("get_stack_content", cached, {"cached": True})

    params = {"order": "desc", "sort": "votes", "filter": "withbody", "site": "stackoverflow"}
    if _STACKEX_KEY:
        params["key"] = _STACKEX_KEY

    data = await _stackex_get(f"/questions/{question_id}", params)
    if not data or not data.get("items"):
        return json_error("get_stack_content", f"question {question_id} not found")

    q = data["items"][0]
    out = [
        f"# {q.get('title', '(no title)')}",
        f"Score: {q.get('score', 0)} | Answers: {q.get('answer_count', 0)} | Views: {q.get('view_count', 0)}",
        f"Tags: {', '.join(q.get('tags', []))}",
        f"Link: {q.get('link', '')}",
        "",
        "--- QUESTION ---",
        re.sub(r"<[^>]+>", "", html_mod.unescape(q.get("body", "") or "")),
    ]

    if include_answers:
        out.append("")
        out.append("--- ANSWERS ---")
        answers_data = await _stackex_get(f"/questions/{question_id}/answers", params)
        if answers_data and answers_data.get("items"):
            answers = answers_data["items"]
            if min_answer_score > 0:
                answers = [a for a in answers if a.get("score", 0) >= min_answer_score]
            for i, a in enumerate(answers[:max_answers], 1):
                out.append("")
                out.append(f"Answer {i}:")
                out.append(_format_answer(a))

    result = "\n".join(out)
    meta = {"quota_remaining": data.get("quota_remaining")}
    cache_set(cache_key, result, ttl=3600)
    return json_ok("get_stack_content", result, meta)
