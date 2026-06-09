import urllib.parse, base64
from . import mcp
from ._client import _get, _format_repo


@mcp.tool(
    name="search_repos",
    description="Cari repository di GitHub berdasarkan query. Parameter sort: stars, updated, forks."
)
async def search_repos(query: str, sort: str = "stars", max_results: int = 10) -> str:
    q = urllib.parse.quote(query)
    data = _get(f"/search/repositories", params={"q": query, "sort": sort, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    items = data.get("items", [])
    if not items:
        return "(no results)"
    results = [f"{i+1}. {_format_repo(r)}" for i, r in enumerate(items[:max_results])]
    return f"Found {data.get('total_count', 0)} repositories:\n\n" + "\n\n".join(results)


@mcp.tool(
    name="get_repo",
    description="Ambil detail repository. Format: owner/repo (contoh: modelcontextprotocol/servers)"
)
async def get_repo(repo: str) -> str:
    data = _get(f"/repos/{repo}")
    if "error" in data:
        return f"(error: {data['error']})"
    return _format_repo(data)


@mcp.tool(
    name="get_file_contents",
    description="Baca isi file dari repository. Format path: owner/repo/path/to/file"
)
async def get_file_contents(repo: str, path: str, branch: str = "main") -> str:
    data = _get(f"/repos/{repo}/contents/{path}", params={"ref": branch})
    if "error" in data:
        return f"(error: {data['error']})"
    if isinstance(data, list):
        entries = "\n".join(f"  {e['name']}/" if e['type'] == 'dir' else f"  {e['name']}" for e in data)
        return f"Directory contents of {path} ({branch}):\n{entries}"
    content_b64 = data.get("content", "")
    if not content_b64:
        return "(empty file or binary)"
    content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
    if len(content) > 5000:
        content = content[:5000] + "\n\n[...truncated]"
    return content


@mcp.tool(
    name="search_code",
    description="Cari kode di GitHub. Parameter: query (contoh: 'function lang:python repo:user/repo')"
)
async def search_code(query: str, max_results: int = 10) -> str:
    data = _get("/search/code", params={"q": query, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    items = data.get("items", [])
    if not items:
        return "(no results)"
    lines = []
    for item in items[:max_results]:
        repo_name = item.get("repository", {}).get("full_name", "?")
        file_path = item.get("path", "?")
        html_url = item.get("html_url", "?")
        lines.append(f"- [{repo_name}] {file_path}\n  {html_url}")
    return f"Found {data.get('total_count', 0)} results:\n\n" + "\n".join(lines)


@mcp.tool(
    name="list_user_repos",
    description="List repository milik user/owner tertentu"
)
async def list_user_repos(owner: str, sort: str = "updated", max_results: int = 20) -> str:
    data = _get(f"/users/{owner}/repos", params={"sort": sort, "per_page": min(max_results, 50)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no repos found)"
    lines = [f"{i+1}. {_format_repo(r)}" for i, r in enumerate(data[:max_results])]
    return "\n\n".join(lines)


@mcp.tool(
    name="get_repository_tree",
    description="Get Git tree for a repo ref. Format repo: owner/repo. Setting recursive=true returns full tree."
)
async def get_repository_tree(repo: str, tree_sha: str = None, recursive: bool = False, path_filter: str = None) -> str:
    params = {}
    if recursive: params["recursive"] = "1"
    ref = tree_sha or "HEAD"
    data = _get(f"/repos/{repo}/git/trees/{ref}", params=params)
    if "error" in data:
        return f"(error: {data['error']})"
    tree = data.get("tree", [])
    if path_filter:
        tree = [t for t in tree if t.get("path", "").startswith(path_filter)]
    lines = [f"  {t['mode']} {t['type'][0].upper()} {t['path']}" for t in tree[:200]]
    summary = f"Tree {data.get('sha', '')[:7]} at {ref} ({len(tree)} entries)"
    if len(tree) > 200:
        lines.append("  ... (truncated)")
    return summary + "\n" + "\n".join(lines)