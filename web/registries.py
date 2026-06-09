"""Package registry search: npm, PyPI, crates.io."""

import re
from urllib.parse import quote_plus

import httpx

from web.cache import get as cache_get, set as cache_set
from web.parsers import json_ok, json_error

_TIMEOUT = httpx.Timeout(10.0)


async def search_npm(query: str, limit: int = 5, detail: bool = False) -> dict:
    """Search npm registry."""
    cache_key = f"mcp:web:npm:search:{query}:{limit}:{detail}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_npm", cached, {"cached": True})

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://registry.npmjs.org/-/v1/search",
                params={"text": query, "size": min(limit, 20)},
            )
            if r.status_code != 200:
                return json_error("search_npm", f"HTTP {r.status_code}")
            data = r.json()
            objects = data.get("objects", [])
            if not objects:
                return json_ok("search_npm", [], {"total": 0})

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
                entry = f"{i}. {name}@{version}\n   {description}\n   Score: {score:.3f} | npm: {npm_link}"
                if repo:
                    entry += f"\n   Repo: {repo}"
                out.append(entry)

            result = "\n\n".join(out)
            cache_set(cache_key, result, ttl=1800)
            return json_ok("search_npm", result, {"total": len(objects)})
        except Exception as e:
            return json_error("search_npm", str(e))


async def search_pypi(query: str, limit: int = 5) -> dict:
    """Search PyPI — exact package lookup first, then prefix fallback."""
    cache_key = f"mcp:web:pypi:search:{query}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_pypi", cached, {"cached": True})

    async def _get_json(url: str) -> dict | None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as c:
            try:
                r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                return r.json() if r.status_code == 200 else None
            except Exception:
                return None

    async def _get_text(url: str) -> str | None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as c:
            try:
                r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                return r.text if r.status_code == 200 else None
            except Exception:
                return None

    # 1. Exact package lookup
    data = await _get_json(f"https://pypi.org/pypi/{quote_plus(query)}/json")
    if data:
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
        return json_ok("search_pypi", result, {"source": "exact"})

    # 2. Prefix search via simple index
    text = await _get_text(f"https://pypi.org/simple/{quote_plus(query)}/")
    if text:
        links = re.findall(rf'href="[^"]*{re.escape(query)}[^"]*"', text, re.IGNORECASE)
        if links:
            result = f"(package '{query}' has {len(links)} release files — use fetch_url for details)"
            cache_set(cache_key, result, ttl=3600)
            return json_ok("search_pypi", result, {"source": "prefix", "files": len(links)})

    # 3. Broad prefix match
    text = await _get_text("https://pypi.org/simple/")
    if text:
        matches = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>\s*([^<]+)\s*</a>', text)
        prefix_matches = [(h, n.strip()) for h, n in matches
                          if n.strip().lower().startswith(query.lower())][:limit]
        if prefix_matches:
            out = []
            for href, name in prefix_matches:
                pkg = await _get_json(f"https://pypi.org/pypi/{quote_plus(name)}/json")
                if pkg:
                    v = pkg.get("info", {}).get("version", "?")
                    d = pkg.get("info", {}).get("summary", "")
                    out.append(f"{name}=={v}\n   {d}")
                else:
                    out.append(name)
            if out:
                result = "\n\n".join(f"{i+1}. {o}" for i, o in enumerate(out))
                cache_set(cache_key, result, ttl=3600)
                return json_ok("search_pypi", result, {"source": "broad_prefix"})

    return json_error("search_pypi",
                      "not found",
                      "Use exact package name or try search_web(query + 'pypi')")


async def search_crates(query: str, limit: int = 5) -> dict:
    """Search crates.io registry."""
    cache_key = f"mcp:web:crates:search:{query}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return json_ok("search_crates", cached, {"cached": True})

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.get(
                "https://crates.io/api/v1/crates",
                params={"q": query, "per_page": min(limit, 20)},
                headers={"User-Agent": "MCPKU/1.0"},
            )
            if r.status_code != 200:
                return json_error("search_crates", f"HTTP {r.status_code}")
            data = r.json()
            crates = data.get("crates", [])
            if not crates:
                return json_ok("search_crates", [], {"total": 0})

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
                out.append(f"{i}. {name} v{version}\n   {description}\n   Downloads: {downloads:,} | {link_text}")

            result = "\n\n".join(out)
            cache_set(cache_key, result, ttl=1800)
            return json_ok("search_crates", result, {"total": len(crates)})
        except Exception as e:
            return json_error("search_crates", str(e))
