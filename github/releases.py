from . import mcp
from ._client import _get, _post, _headers, API_BASE
import requests

@mcp.tool(
    name="list_releases",
    description="List releases dari repository. Format repo: owner/repo"
)
async def list_releases(repo: str, max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/releases", params={"per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no releases)"
    lines = [f"  {r['tag_name']} - {r['name']} ({r['published_at'][:10]})\n    {r['html_url']}" for r in data[:max_results]]
    return f"Releases for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="get_release",
    description="Ambil detail release berdasarkan tag. Format repo: owner/repo"
)
async def get_release(repo: str, tag: str) -> str:
    data = _get(f"/repos/{repo}/releases/tags/{tag}")
    if "error" in data:
        return f"(error: {data['error']})"
    return (
        f"{data['tag_name']} - {data['name']}\n"
        f"Published: {data['published_at']} by {data['author']['login']}\n"
        f"Body: {(data.get('body') or '')[:1000]}\n"
        f"{data['html_url']}"
    )

@mcp.tool(
    name="create_release",
    description="Buat release baru. Format repo: owner/repo"
)
async def create_release(repo: str, tag_name: str, name: str = "", body: str = "", draft: bool = False, prerelease: bool = False) -> str:
    data = _post(f"/repos/{repo}/releases", {"tag_name": tag_name, "name": name, "body": body, "draft": draft, "prerelease": prerelease})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Release created: {data['tag_name']}\\n{data['html_url']}"

@mcp.tool(
    name="list_security_advisories",
    description="List security advisories. Format repo: owner/repo. Type: reviewed, unreviewed"
)
async def list_security_advisories(repo: str, state: str = "published", max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/security-advisories", params={"state": state, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no advisories)"
    lines = [f"  {a.get('ghsa_id', '?')} - {a.get('summary', '?')}\n    Severity: {a.get('severity', '?')} | Published: {a.get('published_at', '?')[:10]}\n    {a.get('html_url', '')}" for a in data[:max_results]]
    return f"Security advisories for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="get_security_advisory",
    description="Get a single security advisory by GHSA ID."
)
async def get_security_advisory(ghsa_id: str) -> str:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v4+json"
    query = '{ securityAdvisory(ghsaId: "%s") { ghsaId summary description severity publishedAt updatedAt identifiers { type value } } }' % ghsa_id
    data = _graphql(query)
    if "error" in data:
        return f"(error: {data['error']})"
    if "errors" in data:
        return f"(error: {data['errors'][0]['message'][:200]})"
    adv = data.get("data", {}).get("securityAdvisory", {})
    if not adv:
        return "(not found)"
    ids = ", ".join(f"{i['type']}: {i['value']}" for i in adv.get("identifiers", []))
    return (
        f"GHSA: {adv.get('ghsaId', '?')}\\n"
        f"Summary: {adv.get('summary', '?')}\\n"
        f"Severity: {adv.get('severity', '?')}\\n"
        f"Identifiers: {ids}\\n"
        f"Description: {(adv.get('description') or '')[:500]}\\n"
        f"Published: {adv.get('publishedAt', '?')}"
    )

@mcp.tool(
    name="list_repo_projects",
    description="List GitHub Projects (classic) for a repository. Format repo: owner/repo"
)
async def list_repo_projects(repo: str, state: str = "open", max_results: int = 10) -> str:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.inertia-preview+json"
    try:
        r = requests.get(f"{API_BASE}/repos/{repo}/projects", headers=headers, params={"state": state, "per_page": min(max_results, 30)}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"(error: {str(e)[:200]})"
    if not data:
        return "(no projects)"
    lines = [f"  {p['name']} - {p.get('body', '')[:100]}\\n    {p['html_url']}" for p in data[:max_results]]
    return f"Projects for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_code_scanning_alerts",
    description="List code scanning alerts. Format repo: owner/repo. State: open, dismissed, fixed"
)
async def list_code_scanning_alerts(repo: str, state: str = "open", max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/code-scanning/alerts", params={"state": state, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no alerts)"
    lines = []
    for a in data[:max_results]:
        rule = a.get("rule", {})
        lines.append(f"  [{rule.get('severity', '?')}] {rule.get('description', '?')}\n    Tool: {a.get('tool', {}).get('name', '?')} | Ref: {a.get('ref', '?')}")
    return f"Code scanning alerts for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_dependabot_alerts",
    description="List Dependabot alerts. Format repo: owner/repo. State: open, dismissed, fixed"
)
async def list_dependabot_alerts(repo: str, state: str = "open", max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/dependabot/alerts", params={"state": state, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no alerts)"
    lines = []
    for a in data[:max_results]:
        sec = a.get("security_advisory", {})
        pkg = a.get("security_vulnerability", {}).get("package", {})
        lines.append(f"  [{sec.get('severity', '?')}] {sec.get('summary', '?')} ({pkg.get('name', '?')} {pkg.get('ecosystem', '?')})\n    {sec.get('description', '')[:200]}")
    return f"Dependabot alerts for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_secret_scanning_alerts",
    description="List secret scanning alerts. Format repo: owner/repo. State: open, resolved"
)
async def list_secret_scanning_alerts(repo: str, state: str = "open", max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/secret-scanning/alerts", params={"state": state, "per_page": min(max_results, 30)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no alerts)"
    lines = [f"  #{a.get('number', '?')} - {a.get('secret_type', '?')} ({a.get('state', '?')})\n    Location: {a.get('location', {}).get('path', '?')}:{a.get('location', {}).get('start_line', '?')}\n    {a.get('html_url', '')}" for a in data[:max_results]]
    return f"Secret scanning alerts for {repo}:\n" + "\n".join(lines)