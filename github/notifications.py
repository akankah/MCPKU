import requests
from . import mcp
from ._client import _get, _post, _patch, _headers, API_BASE

@mcp.tool(
    name="list_notifications",
    description="List notifikasi untuk authenticated user. all: true untuk semua termasuk read"
)
async def list_notifications(all: bool = False, max_results: int = 10) -> str:
    params = {"per_page": min(max_results, 50)}
    if all: params["all"] = "true"
    data = _get("/notifications", params=params)
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no notifications)"
    lines = []
    for n in data[:max_results]:
        repo = n.get("repository", {}).get("full_name", "?")
        subject = n.get("subject", {})
        lines.append(f"  [{n.get('reason', '?')}] {subject.get('type', '?')}: {subject.get('title', '?')}\\n    Repo: {repo} | Updated: {n.get('updated_at', '?')}")
    return f"Notifications:\\n" + "\\n".join(lines)

@mcp.tool(
    name="mark_notification_read",
    description="Tandai notifikasi sebagai sudah dibaca (last_read_at ISO 8601) atau semuanya"
)
async def mark_notification_read(last_read_at: str = None) -> str:
    if last_read_at:
        data = _put("/notifications", {"last_read_at": last_read_at})
    else:
        data = _get("/notifications")
    if not data.get("error"):
        return "Notifications marked as read"
    return f"(error: {data.get('error', 'unknown error')})"

@mcp.tool(
    name="mark_repo_notifications_read",
    description="Mark all notifications as read in a repository. Format repo: owner/repo"
)
async def mark_repo_notifications_read(repo: str, last_read_at: str = None) -> str:
    params = {}
    if last_read_at: params["last_read_at"] = last_read_at
    data = _get(f"/repos/{repo}/notifications", params=params)
    if not data.get("error"):
        return f"Notifications in {repo} marked as read"
    return f"(error: {data.get('error', 'unknown error')})"

@mcp.tool(
    name="mark_thread_read",
    description="Mark a notification thread as read by thread ID."
)
async def mark_thread_read(thread_id: int) -> str:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    try:
        r = requests.patch(f"{API_BASE}/notifications/threads/{thread_id}", headers=headers, timeout=15)
        if r.status_code == 205:
            return f"Thread {thread_id} marked as read"
        return f"(status: {r.status_code})"
    except Exception as e:
        return f"(error: {str(e)[:200]})"