import urllib.parse
from . import mcp
from ._client import _get, _post, _patch, _delete


@mcp.tool(
    name="list_labels",
    description="List labels dari repository. Format repo: owner/repo"
)
async def list_labels(repo: str, max_results: int = 30) -> str:
    data = _get(f"/repos/{repo}/labels", params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no labels)"
    lines = [f"  [{l['name']}] ({l.get('description', '')}) color: {l['color']}" for l in data[:max_results]]
    return f"Labels for {repo}:\n" + "\n".join(lines)


@mcp.tool(
    name="create_label",
    description="Buat label baru di repository. Format repo: owner/repo. Color: hex tanpa #"
)
async def create_label(repo: str, name: str, color: str, description: str = "") -> str:
    data = _post(f"/repos/{repo}/labels", {"name": name, "color": color, "description": description})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Label created: {data['name']} (color: #{data['color']})"


@mcp.tool(
    name="add_labels_to_issue",
    description="Tambahkan label ke issue. Format repo: owner/repo"
)
async def add_labels_to_issue(repo: str, issue_number: int, labels: list) -> str:
    data = _post(f"/repos/{repo}/issues/{issue_number}/labels", {"labels": labels})
    if "error" in data:
        return f"(error: {data['error']})"
    names = ", ".join(l["name"] for l in data)
    return f"Labels added to #{issue_number}: {names}"


@mcp.tool(
    name="remove_label_from_issue",
    description="Hapus label dari issue. Format repo: owner/repo"
)
async def remove_label_from_issue(repo: str, issue_number: int, label: str) -> str:
    data = _delete(f"/repos/{repo}/issues/{issue_number}/labels/{urllib.parse.quote(label)}")
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Label '{label}' removed from #{issue_number}"


@mcp.tool(
    name="get_label",
    description="Get a single label from repository. Format repo: owner/repo"
)
async def get_label(repo: str, name: str) -> str:
    data = _get(f"/repos/{repo}/labels/{urllib.parse.quote(name)}")
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Label: [{data['name']}] color: #{data['color']} description: {data.get('description', '')}"


@mcp.tool(
    name="update_label",
    description="Update label (name, color, description). Format repo: owner/repo"
)
async def update_label(repo: str, current_name: str, new_name: str = None, color: str = None, description: str = None) -> str:
    payload = {}
    if new_name: payload["new_name"] = new_name
    if color: payload["color"] = color
    if description is not None: payload["description"] = description
    data = _patch(f"/repos/{repo}/labels/{urllib.parse.quote(current_name)}", payload)
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Label updated: [{data['name']}] color: #{data['color']}"


@mcp.tool(
    name="delete_label",
    description="Delete a label from repository. Format repo: owner/repo"
)
async def delete_label(repo: str, name: str) -> str:
    data = _delete(f"/repos/{repo}/labels/{urllib.parse.quote(name)}")
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Label '{name}' deleted"