import os, json, base64, urllib.parse
import requests
from pathlib import Path
# Load .env if present
env_path = Path(__file__).parent / ".env"
if env_path.is_file():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
from mcp.server.fastmcp import FastMCP

GITHUB_TOKEN = os.environ.get("GITHUB_API_KEY", "")
API_BASE = "https://api.github.com"

mcp = FastMCP("github", instructions="""
GitHub API tools. Search repos, read files, manage issues, PRs, releases, gists,
discussions, notifications, organizations, labels, actions workflows, and more.
Requires GITHUB_API_KEY environment variable.
""")

def _headers():
    h = {
        "User-Agent": "mcp-github-server",
        "Accept": "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def _get(path, params=None):
    url = f"{API_BASE}{path}"
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300]
        return {"error": f"HTTP {e.response.status_code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

def _post(path, data=None):
    url = f"{API_BASE}{path}"
    try:
        r = requests.post(url, headers=_headers(), json=data, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300]
        return {"error": f"HTTP {e.response.status_code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

def _patch(path, data):
    url = f"{API_BASE}{path}"
    try:
        r = requests.patch(url, headers=_headers(), json=data, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300]
        return {"error": f"HTTP {e.response.status_code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

def _put(path, data=None):
    url = f"{API_BASE}{path}"
    try:
        r = requests.put(url, headers=_headers(), json=data, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300]
        return {"error": f"HTTP {e.response.status_code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

def _delete(path):
    url = f"{API_BASE}{path}"
    try:
        r = requests.delete(url, headers=_headers(), timeout=15)
        if r.status_code != 204:
            return r.json()
        return {"deleted": True}
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300]
        return {"error": f"HTTP {e.response.status_code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

def _format_repo(r):
    return (
        f"Name: {r.get('full_name')}\n"
        f"Description: {r.get('description', '')}\n"
        f"Stars: {r.get('stargazers_count')} | Forks: {r.get('forks_count')} | Language: {r.get('language')}\n"
        f"URL: {r.get('html_url')}\n"
        f"Topics: {', '.join(r.get('topics', []))}\n"
        f"Created: {r.get('created_at')} | Updated: {r.get('updated_at')}"
    )

# ── Existing tools ──────────────────────────────────────────────────────

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

# ── New tools ───────────────────────────────────────────────────────────

# ── Issue / PR comments ────────────────────────────────────────────────

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

# ── Labels ──────────────────────────────────────────────────────────────

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

# ── PR operations ───────────────────────────────────────────────────────

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

# ── Releases ────────────────────────────────────────────────────────────

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
    return f"Release created: {data['tag_name']}\n{data['html_url']}"

# ── Notifications ───────────────────────────────────────────────────────

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
        lines.append(f"  [{n.get('reason', '?')}] {subject.get('type', '?')}: {subject.get('title', '?')}\n    Repo: {repo} | Updated: {n.get('updated_at', '?')}")
    return f"Notifications:\n" + "\n".join(lines)

@mcp.tool(
    name="mark_notification_read",
    description="Tandai notifikasi sebagai sudah dibaca (last_read_at ISO 8601) atau semuanya"
)
async def mark_notification_read(last_read_at: str = None) -> str:
    payload = {}
    if last_read_at: payload["last_read_at"] = last_read_at
    r = None
    if payload:
        r = requests.put(f"{API_BASE}/notifications", headers=_headers(), json=payload, timeout=15)
    else:
        r = requests.put(f"{API_BASE}/notifications", headers=_headers(), timeout=15)
    if r.status_code == 205:
        return "Notifications marked as read"
    return f"(status: {r.status_code})"

# ── Stargazers ──────────────────────────────────────────────────────────

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

# ── Organizations ───────────────────────────────────────────────────────

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

# ── Gists ───────────────────────────────────────────────────────────────

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
    lines = [f"  {g['id']} - {g.get('description', '(no desc)')}\n    Files: {', '.join(g['files'].keys())}\n    {g['html_url']}" for g in data[:max_results]]
    return f"Gists:\n" + "\n".join(lines)

@mcp.tool(
    name="get_gist",
    description="Ambil detail gist berdasarkan ID"
)
async def get_gist(gist_id: str) -> str:
    data = _get(f"/gists/{gist_id}")
    if "error" in data:
        return f"(error: {data['error']})"
    desc = data.get("description") or "(no description)"
    files = "\n".join(f"  {name}: {info.get('content', '')[:500]}" for name, info in data.get("files", {}).items())
    return f"Gist {data['id']}: {desc}\nBy: {data['owner']['login']} | Updated: {data['updated_at']}\n{data['html_url']}\n\nFiles:\n{files}"

@mcp.tool(
    name="create_gist",
    description="Buat gist baru. files adalah dict {'filename': {'content': '...'}}"
)
async def create_gist(files: dict, description: str = "", public: bool = False) -> str:
    data = _post("/gists", {"description": description, "public": public, "files": files})
    if "error" in data:
        return f"(error: {data['error']})"
    return f"Gist created: {data['html_url']}"

# ── Discussions ─────────────────────────────────────────────────────────

@mcp.tool(
    name="list_discussions",
    description="List discussions dari repository. Format repo: owner/repo (perlu GitHub GraphQL API)"
)
async def list_discussions(repo: str, max_results: int = 10) -> str:
    query = """
    {
      repository(owner: \"%s\", name: \"%s\") {
        discussions(first: %d) {
          nodes {
            number title createdAt author { login }
            bodyText
            url
          }
        }
      }
    }
    """ % (repo.split("/")[0], repo.split("/")[1], min(max_results, 50))
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v4+json"
    headers["GraphQL-Features"] = "discussions_api"
    try:
        r = requests.post(f"{API_BASE}/graphql", headers=headers, json={"query": query}, timeout=15)
        r.raise_for_status()
        result = r.json()
    except Exception as e:
        return f"(error: {str(e)[:200]})"
    if "errors" in result:
        return f"(error: {result['errors'][0]['message'][:200]})"
    nodes = result.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
    if not nodes:
        return "(no discussions)"
    lines = [f"  #{d['number']} {d['title']} by {d['author']['login'] if d.get('author') else '?'}\n    {(d.get('bodyText') or '')[:200]}\n    {d['url']}" for d in nodes]
    return f"Discussions for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="create_discussion",
    description="Buat discussion baru. Format repo: owner/repo. category_id dapat dari list_discussion_categories"
)
async def create_discussion(repo: str, title: str, body: str, category_id: str) -> str:
    query = """
    mutation {
      createDiscussion(input: {repositoryId: \"%s\", title: \"%s\", body: \"%s\", categoryId: \"%s\"}) {
        discussion { number title url }
      }
    }
    """ % (repo, title.replace('"', '\\"'), body.replace('"', '\\"'), category_id)
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v4+json"
    try:
        r = requests.post(f"{API_BASE}/graphql", headers=headers, json={"query": query}, timeout=15)
        r.raise_for_status()
        result = r.json()
    except Exception as e:
        return f"(error: {str(e)[:200]})"
    if "errors" in result:
        return f"(error: {result['errors'][0]['message'][:200]})"
    d = result.get("data", {}).get("createDiscussion", {}).get("discussion", {})
    return f"Discussion created: #{d.get('number')} {d.get('title')}\n{d.get('url')}"

# ── Actions / Workflows ─────────────────────────────────────────────────

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

# ── Git data ────────────────────────────────────────────────────────────

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

# ── Code Scanning & Dependabot ──────────────────────────────────────────

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

# ── Context (authenticated user) ─────────────────────────────────────────

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

# ── Actions: run & logs ───────────────────────────────────────────────────

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

# ── Issues: search ────────────────────────────────────────────────────────

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

# ── Git: repository tree ──────────────────────────────────────────────────

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

# ── Labels: update, delete, get single ────────────────────────────────────

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

# ── Gists: update ─────────────────────────────────────────────────────────

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

# ── Discussions: full management ──────────────────────────────────────────

def _graphql(query: str) -> dict:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v4+json"
    try:
        r = requests.post(f"{API_BASE}/graphql", headers=headers, json={"query": query}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)[:200]}

@mcp.tool(
    name="list_discussion_categories",
    description="List discussion categories for a repository. Format repo: owner/repo"
)
async def list_discussion_categories(repo: str) -> str:
    owner, name = repo.split("/")[0], repo.split("/")[1]
    query = '{ repository(owner: "%s", name: "%s") { discussionCategories(first: 50) { nodes { id name slug } } } }' % (owner, name)
    result = _graphql(query)
    if "error" in result:
        return f"(error: {result['error']})"
    if "errors" in result:
        return f"(error: {result['errors'][0]['message'][:200]})"
    cats = result.get("data", {}).get("repository", {}).get("discussionCategories", {}).get("nodes", [])
    if not cats:
        return "(no categories)"
    lines = [f"  {c['name']} (id: {c['id']}, slug: {c['slug']})" for c in cats]
    return f"Discussion categories for {repo}:\n" + "\n".join(lines)

@mcp.tool(
    name="get_discussion",
    description="Get a single discussion by number. Format repo: owner/repo"
)
async def get_discussion(repo: str, discussion_number: int) -> str:
    owner, name = repo.split("/")[0], repo.split("/")[1]
    query = '{ repository(owner: "%s", name: "%s") { discussion(number: %d) { number title bodyText createdAt author { login } url } } }' % (owner, name, discussion_number)
    result = _graphql(query)
    if "error" in result:
        return f"(error: {result['error']})"
    if "errors" in result:
        return f"(error: {result['errors'][0]['message'][:200]})"
    d = result.get("data", {}).get("repository", {}).get("discussion", {})
    if not d:
        return "(discussion not found)"
    return (
        f"#{d['number']} {d['title']}\n"
        f"By: {d['author']['login'] if d.get('author') else '?'} | {d['createdAt']}\n"
        f"Body: {d.get('bodyText', '')[:500]}\n"
        f"{d['url']}"
    )

@mcp.tool(
    name="get_discussion_comments",
    description="Get comments for a discussion. Format repo: owner/repo"
)
async def get_discussion_comments(repo: str, discussion_number: int, max_results: int = 10) -> str:
    owner, name = repo.split("/")[0], repo.split("/")[1]
    query = '{ repository(owner: "%s", name: "%s") { discussion(number: %d) { comments(first: %d) { nodes { id bodyText author { login } createdAt } } } } }' % (owner, name, discussion_number, min(max_results, 50))
    result = _graphql(query)
    if "error" in result:
        return f"(error: {result['error']})"
    if "errors" in result:
        return f"(error: {result['errors'][0]['message'][:200]})"
    nodes = result.get("data", {}).get("repository", {}).get("discussion", {}).get("comments", {}).get("nodes", [])
    if not nodes:
        return "(no comments)"
    lines = [f"  {c['author']['login'] if c.get('author') else '?'} ({c['createdAt'][:10]}): {(c.get('bodyText') or '')[:200]}" for c in nodes]
    return f"Comments for discussion #{discussion_number}:\n" + "\n".join(lines)

@mcp.tool(
    name="add_discussion_comment",
    description="Add a comment to a discussion. Format repo: owner/repo"
)
async def add_discussion_comment(repo: str, discussion_number: int, body: str) -> str:
    owner, name = repo.split("/")[0], repo.split("/")[1]
    # Get discussion ID first
    q = '{ repository(owner: "%s", name: "%s") { discussion(number: %d) { id } } }' % (owner, name, discussion_number)
    r = _graphql(q)
    if "errors" in r:
        return f"(error: {r['errors'][0]['message'][:200]})"
    disc_id = r.get("data", {}).get("repository", {}).get("discussion", {}).get("id", "")
    if not disc_id:
        return "(discussion not found)"
    mutation = 'mutation { addDiscussionComment(input: {discussionId: "%s", body: "%s"}) { comment { id url } } }' % (disc_id, body.replace('"', '\\"').replace("\n", "\\n"))
    result = _graphql(mutation)
    if "errors" in result:
        return f"(error: {result['errors'][0]['message'][:200]})"
    comment = result.get("data", {}).get("addDiscussionComment", {}).get("comment", {})
    return f"Comment added: {comment.get('url', '')}"

# ── Notifications: repo-level ─────────────────────────────────────────────

@mcp.tool(
    name="mark_repo_notifications_read",
    description="Mark all notifications as read in a repository. Format repo: owner/repo"
)
async def mark_repo_notifications_read(repo: str, last_read_at: str = None) -> str:
    payload = {}
    if last_read_at: payload["last_read_at"] = last_read_at
    try:
        r = requests.put(f"{API_BASE}/repos/{repo}/notifications", headers=_headers(), json=payload if payload else None, timeout=15)
        if r.status_code == 205:
            return f"Notifications in {repo} marked as read"
        return f"(status: {r.status_code})"
    except Exception as e:
        return f"(error: {str(e)[:200]})"

@mcp.tool(
    name="mark_thread_read",
    description="Mark a notification thread as read by thread ID."
)
async def mark_thread_read(thread_id: int) -> str:
    try:
        r = requests.patch(f"{API_BASE}/notifications/threads/{thread_id}", headers=_headers(), timeout=15)
        if r.status_code == 205:
            return f"Thread {thread_id} marked as read"
        return f"(status: {r.status_code})"
    except Exception as e:
        return f"(error: {str(e)[:200]})"

# ── Secret Scanning ───────────────────────────────────────────────────────

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

# ── Security Advisories ──────────────────────────────────────────────────

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
        f"GHSA: {adv.get('ghsaId', '?')}\n"
        f"Summary: {adv.get('summary', '?')}\n"
        f"Severity: {adv.get('severity', '?')}\n"
        f"Identifiers: {ids}\n"
        f"Description: {(adv.get('description') or '')[:500]}\n"
        f"Published: {adv.get('publishedAt', '?')}"
    )

# ── Projects ─────────────────────────────────────────────────────────────

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
    lines = [f"  {p['name']} - {p.get('body', '')[:100]}\n    {p['html_url']}" for p in data[:max_results]]
    return f"Projects for {repo}:\n" + "\n".join(lines)

if __name__ == "__main__":
    mcp.run(transport="stdio")
