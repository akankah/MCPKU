import urllib.parse
from . import mcp
from ._client import _get, _post, _patch

@mcp.tool(
    name="list_gists",
    description="List gists untuk user tertentu. Jika username kosong, list gists authenticated user"
)
async def list_gists(username: str = "", max_results: int = 10) -> str:
    path = f"/users/{username}/gists" if username else "/gists"
    data = _get(path, params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no gists)"
    lines = [f"  {g['id']} - {g.get('description', '(no desc)')}\\n    Files: {', '.join(g['files'].keys())}\\n    {g['html_url']}" for g in data[:max_results]]
    return f"Gists:\\n" + "\\n".join(lines)

@mcp.tool(
    name="get_gist",
    description="Ambil detail gist berdasarkan ID"
)
async def get_gist(gist_id: str) -> str:
    data = _get(f"/gists/{gist_id}")
    if "error" in data:
        return f"(error: {data['error']})"
    desc = data.get("description") or "(no description)"
    files = "\\n".join(f"  {name}: {info.get('content', '')[:500]}" for name, info in data.get("files", {}).items())
    return f"Gist {data['id']}: {desc}\\nBy: {data['owner']['login']} | Updated: {data['updated_at']}\\n{data['html_url']}\\n\\nFiles:\\n{files}"

@mcp.tool(
    name="create_gist",
    description="Buat gist baru. files adalah dict {'filename': {'content': '...'}}"
)
async def create_gist(files: dict, description: str = "", public: bool = False) -> str:
    data = _post("/gists", {"description": description, "public": public, "files": files})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Gist created: {data['html_url']}"

@mcp.tool(
    name="update_gist",
    description="Update an existing gist (content and/or description)."
)
async def update_gist(gist_id: str, content: str, filename: str = None, description: str = None) -> str:
    payload = {"files": {}}
    key = filename or "file"
    payload["files"][key] = {"content": content}
    if description is not None: payload["description"] = description
    data = _patch(f"/gists/{gist_id}", payload)
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Gist updated: {data['html_url']}"