from . import mcp
from ._client import _get, _post, _patch


@mcp.tool(
    name="list_issues",
    description="List issues dari repository. Format: owner/repo. State: open, closed, all."
)
async def list_issues(repo: str, state: str = "open", max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/issues", params={"state": state, "per_page": min(max_results, 30), "sort": "updated"})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no issues)"
    results = []
    for issue in data[:max_results]:
        label_str = ", ".join(l["name"] for l in issue.get("labels", []))
        labels = f" [{label_str}]" if label_str else ""
        results.append(
            f"#{issue['number']} {issue['title']}{labels}\n"
            f"  State: {issue['state']} | By: {issue['user']['login']}\n"
            f"  {issue['html_url']}"
        )
    return "\n\n".join(results)


@mcp.tool(
    name="create_issue",
    description="Buat issue baru di repository. Format repo: owner/repo"
)
async def create_issue(repo: str, title: str, body: str = "") -> str:
    data = _post(f"/repos/{repo}/issues", {"title": title, "body": body})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Issue created: #{data.get('number')} {data.get('title')}\n{data.get('html_url')}"


@mcp.tool(
    name="update_issue",
    description="Update issue (title, body, state, assignees, labels). Format repo: owner/repo"
)
async def update_issue(repo: str, issue_number: int, title: str = None, body: str = None, state: str = None, labels: list = None) -> str:
    payload = {}
    if title is not None: payload["title"] = title
    if body is not None: payload["body"] = body
    if state is not None: payload["state"] = state
    if labels is not None: payload["labels"] = labels
    data = _patch(f"/repos/{repo}/issues/{issue_number}", payload)
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Issue #{data['number']} updated: {data['html_url']}"


@mcp.tool(
    name="list_issue_comments",
    description="List komentar dari issue. Format repo: owner/repo"
)
async def list_issue_comments(repo: str, issue_number: int, max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/issues/{issue_number}/comments", params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no comments)"
    results = []
    for c in data[:max_results]:
        results.append(
            f"By: {c['user']['login']} | {c['created_at']}\n"
            f"{(c.get('body') or '')[:300]}\n"
        )
    return "\n---\n".join(results)


@mcp.tool(
    name="add_issue_comment",
    description="Tambahkan komentar pada issue. Format repo: owner/repo"
)
async def add_issue_comment(repo: str, issue_number: int, body: str) -> str:
    data = _post(f"/repos/{repo}/issues/{issue_number}/comments", {"body": body})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Comment added: {data.get('html_url')}"


@mcp.tool(
    name="search_issues",
    description="Search issues/PRs using GitHub issues search syntax (qualifiers: repo, label, author, is:issue, is:pr, etc.)."
)
async def search_issues(query: str, max_results: int = 10, sort: str = None, order: str = None) -> str:
    params = {"q": query, "per_page": min(max_results, 100)}
    if sort: params["sort"] = sort
    if order: params["order"] = order
    data = _get("/search/issues", params=params)
    if "error" in data:
        return f"(error: {data['error']})"
    items = data.get("items", [])
    if not items:
        return "(no results)"
    results = []
    for item in items[:max_results]:
        label_str = ", ".join(l["name"] for l in item.get("labels", []))
        labels = f" [{label_str}]" if label_str else ""
        results.append(
            f"#{item['number']} {item['title']}{labels}\n"
            f"  State: {item['state']} | By: {item['user']['login']}\n"
            f"  {item['html_url']}"
        )
    return f"Found {data.get('total_count', 0)} results:\n\n" + "\n\n".join(results)