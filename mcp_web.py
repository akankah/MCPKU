import os, re, html, json
from urllib.parse import quote_plus, urlencode
from mcp.server.fastmcp import FastMCP
import asyncio
import requests
from mcp_cache import cache_get, cache_set

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
STACKEX_API_KEY = os.environ.get("STACKEX_API_KEY", "")
_DDG_ENABLED = os.environ.get("DISABLE_DUCKDUCKGO", "0") != "1"

mcp = FastMCP("web-tools", instructions="""
Web fetch and search tools for real-time information. fetch_url extracts
content as clean text/markdown. search_web uses DuckDuckGo (free, no key)
with Firecrawl fallback if configured.

Stack Exchange tools (search_stackoverflow, get_stack_content) use the
official Stack Exchange API with 10,000 requests/day quota.

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
            def _firecrawl_call():
                return requests.post(
                    "https://api.firecrawl.dev/v1/search",
                    json={"query": query},
                    headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"},
                    timeout=15,
                )
            r = await asyncio.to_thread(_firecrawl_call)
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

# ---------------------------------------------------------------------------
# Stack Exchange API tools (search Stack Overflow, get questions/answers)
# Docs: https://api.stackexchange.com/docs
# Set STACKEX_API_KEY env var for 10,000 requests/day quota.
# ---------------------------------------------------------------------------

_STACKEX_BASE = "https://api.stackexchange.com/2.3"

def _stackex_get(path: str, params: dict) -> dict | None:
    params.setdefault("key", STACKEX_API_KEY)
    params.setdefault("site", "stackoverflow")
    try:
        r = requests.get(f"{_STACKEX_BASE}{path}", params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
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
    body = html.unescape(body)[:2000]
    return f"[{score} votes{accepted}] by {owner}\n{body}\n"

@mcp.tool(
    name="search_stackoverflow",
    description="Cari pertanyaan di Stack Overflow via API resmi. Hasil diurutkan berdasarkan relevance."
    " Gunakan filter tag, score minimal, atau kata kunci spesifik untuk hasil lebih akurat."
)
async def search_stackoverflow(
    query: str,
    max_results: int = 5,
    tags: str = "",
    min_score: int = 0,
    sort: str = "relevance",
) -> str:
    cache_key = f"mcp:web:so:search:{query}:{tags}:{min_score}:{sort}:{max_results}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "q": query,
        "sort": sort,
        "order": "desc",
        "pagesize": min(max_results, 20),
        "filter": "withbody",
        "site": "stackoverflow",
    }
    if STACKEX_API_KEY:
        params["key"] = STACKEX_API_KEY
    if tags:
        params["tagged"] = tags

    data = await asyncio.to_thread(_stackex_get, "/search/advanced", params)
    if not data:
        return "(Stack Exchange API error or no response)"

    items = data.get("items", [])
    if not items:
        return "(no results found)"

    if min_score > 0:
        items = [i for i in items if i.get("score", 0) >= min_score]

    if not items:
        return f"(no results with score >= {min_score})"

    out_parts = []
    for i, item in enumerate(items[:max_results], 1):
        out_parts.append(f"{i}. {_format_question(item)}")

    # Rate limit info
    quota = data.get("quota_remaining", "?")
    result = "\n\n".join(out_parts)
    result += f"\n\n(API calls remaining: {quota})"

    cache_set(cache_key, result, ttl=3600)
    return result


@mcp.tool(
    name="get_stack_content",
    description="Ambil detail pertanyaan + jawaban dari Stack Exchange berdasarkan ID."
    " Bisa juga ambil langsung dari URL Stack Overflow (parse otomatis ID-nya)."
)
async def get_stack_content(
    question_id: int | str = "",
    url: str = "",
    include_answers: bool = True,
    max_answers: int = 3,
    min_answer_score: int = 0,
) -> str:
    if url and not question_id:
        m = re.search(r"(?:questions|q)/(\d+)", url)
        if m:
            question_id = int(m.group(1))
        else:
            return "(could not parse question ID from URL)"

    if not question_id:
        return "(provide question_id or url)"

    cache_key = f"mcp:web:so:get:{question_id}:{include_answers}:{max_answers}:{min_answer_score}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch question
    params = {"order": "desc", "sort": "votes", "filter": "withbody", "site": "stackoverflow"}
    if STACKEX_API_KEY:
        params["key"] = STACKEX_API_KEY
    data = _stackex_get(f"/questions/{question_id}", params)
    if not data or not data.get("items"):
        return f"(question {question_id} not found)"

    q = data["items"][0]
    out = [
        f"# {q.get('title', '(no title)')}",
        f"Score: {q.get('score', 0)} | Answers: {q.get('answer_count', 0)} | "
        f"Views: {q.get('view_count', 0)}",
        f"Tags: {', '.join(q.get('tags', []))}",
        f"Link: {q.get('link', '')}",
        "",
        "--- QUESTION ---",
        re.sub(r"<[^>]+>", "", html.unescape(q.get("body", "") or "")),
    ]

    if include_answers:
        out.append("")
        out.append("--- ANSWERS ---")
        answers_data = _stackex_get(f"/questions/{question_id}/answers", params)
        if answers_data and answers_data.get("items"):
            answers = answers_data["items"]
            if min_answer_score > 0:
                answers = [a for a in answers if a.get("score", 0) >= min_answer_score]
            for i, a in enumerate(answers[:max_answers], 1):
                out.append("")
                out.append(f"Answer {i}:")
                out.append(_format_answer(a))

    quota = data.get("quota_remaining", "?")
    result = "\n".join(out)
    result += f"\n\n(API calls remaining: {quota})"

    cache_set(cache_key, result, ttl=3600)
    return result


# ---------------------------------------------------------------------------
# Package registry search tools (npm, PyPI, crates.io)
# All free, no API key required.
# ---------------------------------------------------------------------------

@mcp.tool(
    name="search_npm",
    description="Cari package di npm registry. Returns nama, versi, deskripsi, link."
)
async def search_npm(query: str, limit: int = 5, detail: bool = False) -> str:
    cache_key = f"mcp:web:npm:search:{query}:{limit}:{detail}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        def _npm_call():
            return requests.get(
                "https://registry.npmjs.org/-/v1/search",
                params={"text": query, "size": min(limit, 20)},
                timeout=10,
            )
        r = await asyncio.to_thread(_npm_call)
        if r.status_code != 200:
            return f"(npm search failed: HTTP {r.status_code})"
        data = r.json()
        objects = data.get("objects", [])
        if not objects:
            return "(no npm packages found)"

        out = []
        for i, obj in enumerate(objects[:limit], 1):
            pkg = obj.get("package", {})
            name = pkg.get("name", "")
            version = pkg.get("version", "")
            description = pkg.get("description", "") or ""
            links = pkg.get("links", {})
            npm_link = links.get("npm", "")
            repo = links.get("repository", "")
            score = obj.get("score", {}).get("final", 0)

            out.append(
                f"{i}. {name}@{version}\n"
                f"   {description}\n"
                f"   Score: {score:.3f} | npm: {npm_link}"
            )
            if repo:
                out[-1] += f"\n   Repo: {repo}"

        result = "\n\n".join(out)
        cache_set(cache_key, result, ttl=1800)
        return result
    except Exception as e:
        return f"(npm search error: {e})"


@mcp.tool(
    name="search_pypi",
    description="Cari package Python di PyPI via JSON API. Cari by nama package (exact atau mirip)."
    " Untuk search keyword gunakan search_web() sebagai alternatif."
)
async def search_pypi(query: str, limit: int = 5) -> str:
    cache_key = f"mcp:web:pypi:search:{query}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        # Try exact package lookup first
        def _pypi_call():
            return requests.get(
                f"https://pypi.org/pypi/{quote_plus(query)}/json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
        r = await asyncio.to_thread(_pypi_call)
        if r.status_code == 200:
            data = r.json()
            info = data.get("info", {})
            name = info.get("name", query)
            version = info.get("version", "")
            summary = info.get("summary", "") or ""
            author = info.get("author", "")
            license_ = info.get("license", "") or ""
            home = info.get("home_page", "") or info.get("project_urls", {}).get("Homepage", "")
            python_req = info.get("requires_python", "") or ""
            pypi_url = f"https://pypi.org/project/{name}/"
            result = (
                f"1. {name}=={version}\n"
                f"   {summary}\n"
                f"   Author: {author} | License: {license_}\n"
                f"   Requires Python: {python_req}\n"
                f"   Home: {home}\n"
                f"   PyPI: {pypi_url}"
            )
            cache_set(cache_key, result, ttl=3600)
            return result

        # Try the /simple/ index for prefix matching
        def _pypi_simple_call():
            return requests.get(
                f"https://pypi.org/simple/{quote_plus(query)}/",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
        r2 = await asyncio.to_thread(_pypi_simple_call)
        if r2.status_code == 200:
            links = re.findall(rf'href="[^"]*{re.escape(query)}[^"]*"', r2.text, re.IGNORECASE)
            if links:
                result = f"(package '{query}' has {len(links)} release files — use fetch_url on its project page for details)"
                cache_set(cache_key, result, ttl=3600)
                return result

    except Exception:
        pass

    # Fallback: try a broad search via simple index prefix
    try:
        first_letter = query[0].lower() if query else "a"
        def _pypi_simple_broad():
            return requests.get(
                f"https://pypi.org/simple/",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
        r3 = await asyncio.to_thread(_pypi_simple_broad)
        if r3.status_code == 200:
            names = re.findall(rf'<a[^>]*href="[^"]*"[^>]*>\s*{re.escape(query.lower())}[^<]*\s*</a>', r3.text)
            if names:
                matches = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>\s*([^<]+)\s*</a>', r3.text)
                prefix_matches = [(h, n.strip()) for h, n in matches
                                  if n.strip().lower().startswith(query.lower())][:limit]
                if prefix_matches:
                    out = []
                    for href, name in prefix_matches:
                        def _pypi_ver(n=name):
                            return requests.get(
                                f"https://pypi.org/pypi/{quote_plus(n)}/json",
                                headers={"User-Agent": "Mozilla/5.0"},
                                timeout=5,
                            )
                        ver_r = await asyncio.to_thread(_pypi_ver)
                        if ver_r.status_code == 200:
                            ver_data = ver_r.json().get("info", {})
                            ver = ver_data.get("version", "?")
                            desc = ver_data.get("summary", "")
                            out.append(f"{name}=={ver}\n   {desc}")
                        else:
                            out.append(name)
                    if out:
                        result = "\n\n".join(f"{i+1}. {o}" for i, o in enumerate(out))
                        cache_set(cache_key, result, ttl=3600)
                        return result
    except Exception:
        pass

    return (
        f"(PyPI search terbatas — PyPI search page requires JavaScript. "
        f"Gunakan search_pypi dengan exact package name, atau search_web(query + 'pypi') untuk alternatif.)"
    )


@mcp.tool(
    name="search_crates",
    description="Cari Rust crate di crates.io. Returns nama, versi, deskripsi, downloads."
)
async def search_crates(query: str, limit: int = 5) -> str:
    cache_key = f"mcp:web:crates:search:{query}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        def _crates_call():
            return requests.get(
                "https://crates.io/api/v1/crates",
                params={"q": query, "per_page": min(limit, 20)},
                headers={"User-Agent": "MCPKU/1.0"},
                timeout=10,
            )
        r = await asyncio.to_thread(_crates_call)
        if r.status_code != 200:
            return f"(crates.io search failed: HTTP {r.status_code})"
        data = r.json()
        crates = data.get("crates", [])
        if not crates:
            return "(no crates found)"

        out = []
        for i, c in enumerate(crates[:limit], 1):
            name = c.get("name", "")
            version = c.get("max_version", "")
            description = c.get("description", "") or ""
            downloads = c.get("downloads", 0)
            docs = c.get("documentation", "")
            home = c.get("homepage", "")
            repo = c.get("repository", "")
            link_text = f"docs: {docs}" if docs else f"repo: {repo}" if repo else ""

            out.append(
                f"{i}. {name} v{version}\n"
                f"   {description}\n"
                f"   Downloads: {downloads:,} | {link_text}"
            )

        result = "\n\n".join(out)
        cache_set(cache_key, result, ttl=1800)
        return result
    except Exception as e:
        return f"(crates.io search error: {e})"


# ---------------------------------------------------------------------------
# Documentation search tools (MDN, DevDocs)
# ---------------------------------------------------------------------------

@mcp.tool(
    name="search_readthedocs",
    description="Cari dokumentasi library Python di ReadTheDocs. Sangat akurat untuk dokumentasi library Python."
)
async def search_readthedocs(query: str, limit: int = 5) -> str:
    # Menggunakan Google Search terbatas pada domain readthedocs.io
    query = f"site:readthedocs.io {query}"
    return await search_web(query, max_results=limit)

@mcp.tool(
    name="search_mdn",
    description="Cari dokumentasi web di MDN (Mozilla Developer Network). Returns title, summary, link."
)
async def search_mdn(query: str, limit: int = 5, locale: str = "en-US") -> str:
    cache_key = f"mcp:web:mdn:search:{query}:{limit}:{locale}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        def _mdn_call():
            return requests.get(
                "https://developer.mozilla.org/api/v1/search",
                params={"q": query, "locale": locale},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
        r = await asyncio.to_thread(_mdn_call)
        if r.status_code != 200:
            return f"(MDN search failed: HTTP {r.status_code})"
        data = r.json()
        docs = data.get("documents", [])
        if not docs:
            return "(no MDN results)"

        out = []
        for i, doc in enumerate(docs[:limit], 1):
            title = doc.get("title", "")
            summary = doc.get("summary", "") or ""
            mdn_url = doc.get("mdn_url", "")
            full_url = f"https://developer.mozilla.org{mdn_url}" if mdn_url else ""
            out.append(f"{i}. {title}\n   {summary[:200]}\n   {full_url}")

        result = "\n\n".join(out)
        cache_set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        return f"(MDN search error: {e})"


@mcp.tool(
    name="search_devdocs",
    description="Cari dokumentasi API di DevDocs.io. List doc sets yang tersedia,"
    " atau cari dengan query + filter by doc set (python, javascript, rust, dll)."
    " Karena DevDocs search bersifat client-side, hasil diformat sebagai link ke DevDocs."
)
async def search_devdocs(query: str = "", doc_filter: str = "", limit: int = 5) -> str:
    cache_key = f"mcp:web:devdocs:search:{query}:{doc_filter}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch available docs list
    try:
        def _devdocs_call():
            return requests.get(
                "https://devdocs.io/docs.json",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
        r = await asyncio.to_thread(_devdocs_call)
        if r.status_code != 200:
            return f"(DevDocs failed: HTTP {r.status_code})"
        all_docs = r.json()
    except Exception as e:
        return f"(DevDocs error: {e})"

    # Filter docs
    if doc_filter:
        matching = [d for d in all_docs if doc_filter.lower() in d.get("slug", "").lower()
                    or doc_filter.lower() in d.get("name", "").lower()]
    else:
        matching = all_docs

    if not matching:
        return f"(no DevDocs doc set matching '{doc_filter}')"

    if not query:
        # Just list available docs
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
        cache_set(cache_key, result, ttl=3600)
        return result

    # Build DevDocs search URLs for each matching doc
    out = [f"DevDocs search results for '{query}' in '{doc_filter or 'all'}':\n"]
    for d in matching[:limit]:
        slug = d.get("slug", "")
        name = d.get("name", "")
        search_url = f"https://devdocs.io/#q={quote_plus(query)}"
        doc_url = f"https://devdocs.io/{slug}/"
        out.append(f"  [{name} ({slug})]")
        out.append(f"    Search: {search_url}")
        out.append(f"    Docs:   {doc_url}")

    out.append(f"\n(Catatan: DevDocs search bersifat client-side — buka link di browser untuk hasil interaktif.)")

    result = "\n".join(out)
    cache_set(cache_key, result, ttl=1800)
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
