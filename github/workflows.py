from . import mcp
from ._client import _get, _post, _headers, API_BASE

@mcp.tool(
    name="list_workflows",
    description="List workflows dari repository. Format repo: owner/repo"
)
async def list_workflows(repo: str, max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/actions/workflows", params={"per_page": min(max_results, 50)})
    if "error" in data:
        return f"(error: {data['error']})"
    workflows = data.get("workflows", [])
    if not workflows:
        return "(no workflows)"
    lines = [f"  {w['name']} ({w['state']}) - {w['path']}" for w in workflows[:max_results]]
    return f"Workflows for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_workflow_runs",
    description="List workflow runs. Format repo: owner/repo. Bisa filter by workflow_id (filename or ID)"
)
async def list_workflow_runs(repo: str, workflow_id: str = None, max_results: int = 10) -> str:
    path = f"/repos/{repo}/actions/runs"
    params = {"per_page": min(max_results, 50)}
    if workflow_id:
        path = f"/repos/{repo}/actions/workflows/{workflow_id}/runs"
    data = _get(path, params=params)
    if "error" in data:
        return f"(error: {data['error']})"
    runs = data.get("workflow_runs", [])
    if not runs:
        return "(no workflow runs)"
    lines = [f"  {r['name'] or r['display_title']} ({r['status']}/{r['conclusion']}) - {r['html_url']}" for r in runs[:max_results]]
    return f"Workflow runs for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_workflow_run_jobs",
    description="List jobs dari workflow run tertentu. Format repo: owner/repo"
)
async def list_workflow_run_jobs(repo: str, run_id: int) -> str:
    data = _get(f"/repos/{repo}/actions/runs/{run_id}/jobs")
    if "error" in data:
        return f"(error: {data['error']})"
    jobs = data.get("jobs", [])
    if not jobs:
        return "(no jobs)"
    lines = [f"  {j['name']} ({j['status']}/{j['conclusion']}) - {j['html_url']}" for j in jobs]
    return f"Jobs for run #{run_id}:\n" + "\n".join(lines)

@mcp.tool(
    name="trigger_workflow",
    description="Trigger a workflow run. Format repo: owner/repo. workflow_id can be numeric ID or filename like 'ci.yml'."
)
async def trigger_workflow(repo: str, workflow_id: str, ref: str = "main", inputs: dict = None) -> str:
    data = _post(f"/repos/{repo}/actions/workflows/{workflow_id}/dispatches", {
        "ref": ref, "inputs": inputs or {}
    })
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Workflow '{workflow_id}' triggered on ref '{ref}'"

@mcp.tool(
    name="get_workflow_run_logs",
    description="Get workflow run logs. Format repo: owner/repo. Use tail_lines to get only last N lines."
)
async def get_workflow_run_logs(repo: str, run_id: int, tail_lines: int = None) -> str:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    try:
        r = requests.get(f"{API_BASE}/repos/{repo}/actions/runs/{run_id}/logs", headers=headers, timeout=30)
        if r.status_code == 302:
            r = requests.get(r.headers["Location"], timeout=30)
        if r.status_code != 200:
            return f"(error: HTTP {r.status_code})"
        text = r.text
        if tail_lines:
            text = "\n".join(text.splitlines()[-tail_lines:])
        if len(text) > 30000:
            text = text[:30000] + "\n\n[...truncated]"
        return text
    except Exception as e:
        return f"(error: {str(e)[:200]})"