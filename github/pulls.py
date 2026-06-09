from . import mcp
from ._client import _get, _post, _patch, _put


@mcp.tool(
    name="list_pull_requests",
    description="List pull requests dari repository. Format: owner/repo. State: open, closed, all."
)
async def list_pull_requests(repo: str, state: str = "open", max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/pulls", params={"state": state, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no pull requests)"
    results = []
    for pr in data[:max_results]:
        results.append(
            f"#{pr['number']} {pr['title']}\n"
            f"  State: {pr['state']} | By: {pr['user']['login']}\n"
            f"  {pr['html_url']}"
        )
    return "\n\n".join(results)


@mcp.tool(
    name="get_pull_request",
    description="Ambil detail pull request. Format repo: owner/repo"
)
async def get_pull_request(repo: str, pr_number: int) -> str:
    data = _get(f"/repos/{repo}/pulls/{pr_number}")
    if "error" in data:
        return f"(error: {data['error']})"
    return (
        f"#{data['number']} {data['title']}\n"
        f"State: {data['state']} | Merged: {data.get('merged', False)}\n"
        f"By: {data['user']['login']} | Base: {data['base']['ref']} <- Head: {data['head']['ref']}\n"
        f"Commits: {data.get('commits', '?')} | Files: {data.get('changed_files', '?')}\n"
        f"Body: {(data.get('body') or '')[:500]}\n"
        f"{data['html_url']}"
    )


@mcp.tool(
    name="create_pull_request",
    description="Buat pull request baru. Format repo: owner/repo"
)
async def create_pull_request(repo: str, title: str, head: str, base: str, body: str = "", draft: bool = False) -> str:
    data = _post(f"/repos/{repo}/pulls", {"title": title, "head": head, "base": base, "body": body, "draft": draft})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"PR #{data['number']} created: {data['title']}\n{data['html_url']}"


@mcp.tool(
    name="merge_pull_request",
    description="Merge pull request. Format repo: owner/repo. Method: merge, squash, rebase"
)
async def merge_pull_request(repo: str, pr_number: int, commit_title: str = None, commit_message: str = "", merge_method: str = "merge") -> str:
    payload = {"commit_message": commit_message, "merge_method": merge_method}
    if commit_title: payload["commit_title"] = commit_title
    data = _put(f"/repos/{repo}/pulls/{pr_number}/merge", payload)
    if "error" in data:
        return f"(error: {data['error']})"
    return f"PR #{pr_number} merged: {data.get('message', '')}\n{data.get('html_url', '')}"


@mcp.tool(
    name="update_pull_request",
    description="Update PR (title, body, state, base branch). Format repo: owner/repo"
)
async def update_pull_request(repo: str, pr_number: int, title: str = None, body: str = None, state: str = None, base: str = None) -> str:
    payload = {}
    if title: payload["title"] = title
    if body is not None: payload["body"] = body
    if state: payload["state"] = state
    if base: payload["base"] = base
    data = _patch(f"/repos/{repo}/pulls/{pr_number}", payload)
    if "error" in data:
        return f"(error: {data['error']})"
    return f"PR #{data['number']} updated: {data['html_url']}"


@mcp.tool(
    name="list_pull_request_files",
    description="List file yang diubah di pull request. Format repo: owner/repo"
)
async def list_pull_request_files(repo: str, pr_number: int) -> str:
    data = _get(f"/repos/{repo}/pulls/{pr_number}/files")
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no files changed)"
    lines = [f"  {f['filename']} (+{f.get('additions',0)}/-{f.get('deletions',0)})" for f in data]
    return f"Files changed in PR #{pr_number} ({len(data)} files):\n" + "\n".join(lines)


@mcp.tool(
    name="list_pull_request_commits",
    description="List commit dari pull request. Format repo: owner/repo"
)
async def list_pull_request_commits(repo: str, pr_number: int) -> str:
    data = _get(f"/repos/{repo}/pulls/{pr_number}/commits")
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no commits)"
    lines = [f"  {c['sha'][:7]} {c['commit']['message'].split(chr(10))[0]} ({c['commit']['author']['name']})" for c in data]
    return f"Commits in PR #{pr_number}:\n" + "\n".join(lines)


@mcp.tool(
    name="add_pull_request_comment",
    description="Tambahkan review comment ke PR (pada baris tertentu). Format repo: owner/repo"
)
async def add_pull_request_comment(repo: str, pr_number: int, body: str, commit_id: str = "", path: str = "", line: int = 0) -> str:
    payload = {"body": body}
    if commit_id: payload["commit_id"] = commit_id
    if path: payload["path"] = path
    if line: payload["line"] = line
    data = _post(f"/repos/{repo}/pulls/{pr_number}/comments", payload)
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Comment added: {data.get('html_url')}"


@mcp.tool(
    name="list_pull_request_reviews",
    description="List reviews dari pull request. Format repo: owner/repo"
)
async def list_pull_request_reviews(repo: str, pr_number: int) -> str:
    data = _get(f"/repos/{repo}/pulls/{pr_number}/reviews")
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no reviews)"
    lines = [f"  {r['user']['login']}: {r['state']} | {r['body'][:100] if r.get('body') else '(no body)'}" for r in data]
    return f"Reviews for PR #{pr_number}:\n" + "\n".join(lines)