from . import mcp
from ._client import _get, _post, _headers, API_BASE

@mcp.tool(
    name="list_branches",
    description="List branches dari repository. Format repo: owner/repo"
)
async def list_branches(repo: str, max_results: int = 20) -> str:
    data = _get(f"/repos/{repo}/branches", params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no branches)"
    lines = [f"  {b['name']}" for b in data[:max_results]]
    return f"Branches for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_tags",
    description="List tags dari repository. Format repo: owner/repo"
)
async def list_tags(repo: str, max_results: int = 20) -> str:
    data = _get(f"/repos/{repo}/tags", params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no tags)"
    lines = [f"  {t['name']}" for t in data[:max_results]]
    return f"Tags for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="create_ref",
    description="Buat reference (branch/tag). Format repo: owner/repo. Ref: refs/heads/branchname atau refs/tags/tagname"
)
async def create_ref(repo: str, ref: str, sha: str) -> str:
    data = _post(f"/repos/{repo}/git/refs", {"ref": ref, "sha": sha})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Ref created: {data['ref']} ({data['object']['sha'][:7]})"

@mcp.tool(
    name="get_commit",
    description="Ambil detail commit. Format repo: owner/repo"
)
async def get_commit(repo: str, sha: str) -> str:
    data = _get(f"/repos/{repo}/git/commits/{sha}")
    if "error" in data:
        return f"(error: {data['error']})"
    return (
        f"Commit: {data['sha']}\n"
        f"Author: {data['author']['name']} <{data['author']['email']}> | {data['author']['date']}\n"
        f"Message: {data['message']}"
    )

@mcp.tool(
    name="get_commit_diff",
    description="Ambil diff antara dua commit/refs. Format repo: owner/repo"
)
async def get_commit_diff(repo: str, base: str, head: str) -> str:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v3.diff"
    try:
        r = requests.get(f"{API_BASE}/repos/{repo}/compare/{base}...{head}", headers=headers, timeout=15)
        if r.status_code != 200:
            return f"(error: HTTP {r.status_code}: {r.text[:200]})"
        diff = r.text
        if len(diff) > 10000:
            diff = diff[:10000] + "\n\n[...diff truncated at 10000 chars]"
        return diff
    except Exception as e:
        return f"(error: {str(e)[:200]})"