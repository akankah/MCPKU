from . import mcp
from ._client import _get

@mcp.tool(
    name="list_org_members",
    description="List anggota organisasi. Format: org-name"
)
async def list_org_members(org: str, max_results: int = 20) -> str:
    data = _get(f"/orgs/{org}/members", params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no members)"
    lines = [f"  {m.get('login', '?')}" for m in data[:max_results]]
    return f"Members of {org}:\n" + "\n".join(lines)

@mcp.tool(
    name="list_org_repos",
    description="List repository organisasi. Format: org-name"
)
async def list_org_repos(org: str, sort: str = "updated", max_results: int = 20) -> str:
    data = _get(f"/orgs/{org}/repos", params={"sort": sort, "per_page": min(max_results, 50)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no repos)"
    lines = [f"{i+1}. {_format_repo(r)}" for i, r in enumerate(data[:max_results])]
    return "\n\n".join(lines)

@mcp.tool(
    name="list_stargazers",
    description="List stargazers dari repository. Format repo: owner/repo"
)
async def list_stargazers(repo: str, max_results: int = 10) -> str:
    data = _get(f"/repos/{repo}/stargazers", params={"per_page": min(max_results, 100)})
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no stargazers)"
    lines = [f"  {s.get('login', '?')}" for s in data[:max_results]]
    return f"Stargazers for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="get_me",
    description="Get authenticated user profile."
)
async def get_me() -> str:
    data = _get("/user")
    if "error" in data:
        return f"(error: {data['error']})"
    return (
        f"Login: {data.get('login')}\n"
        f"Name: {data.get('name', 'N/A')}\n"
        f"Email: {data.get('email', 'N/A')}\n"
        f"Bio: {data.get('bio', 'N/A')}\n"
        f"Public repos: {data.get('public_repos')} | Followers: {data.get('followers')}\n"
        f"{data.get('html_url')}"
    )

@mcp.tool(
    name="get_teams",
    description="Get teams for the authenticated user or a specific user."
)
async def get_teams(user: str = None) -> str:
    path = f"/users/{user}/teams" if user else "/user/teams"
    data = _get(path)
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no teams)"
    lines = [f"  {t['name']} @ {t['organization']['login']} ({t['slug']})" for t in data]
    return f"Teams:\n" + "\n".join(lines)

@mcp.tool(
    name="get_team_members",
    description="Get members of a team. Format org/team_slug."
)
async def get_team_members(org: str, team_slug: str) -> str:
    data = _get(f"/orgs/{org}/teams/{team_slug}/members")
    if "error" in data:
        return f"(error: {data['error']})"
    if not data:
        return "(no members)"
    lines = [f"  {m['login']}" for m in data]
    return f"Members of {org}/{team_slug}:\n" + "\n".join(lines)

@mcp.tool(
    name="get_user",
    description="Get public profile for any GitHub user."
)
async def get_user(username: str) -> str:
    data = _get(f"/users/{username}")
    if "error" in data:
        return f"(error: {data['error']})"
    return (
        f"Login: {data.get('login')}\n"
        f"Name: {data.get('name', 'N/A')}\n"
        f"Company: {data.get('company', 'N/A')}\n"
        f"Location: {data.get('location', 'N/A')}\n"
        f"Bio: {data.get('bio', 'N/A')}\n"
        f"Public repos: {data.get('public_repos')} | Followers: {data.get('followers')} | Following: {data.get('following')}\n"
        f"Created: {data.get('created_at')}\n"
        f"{data.get('html_url')}"
    )