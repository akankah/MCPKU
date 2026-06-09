from . import mcp
from ._client import _headers, _graphql

@mcp.tool(
    name="list_discussions",
    description="List discussions dari repository. Format repo: owner/repo (perlu GitHub GraphQL API)"
)
async def list_discussions(repo: str, max_results: int = 10) -> str:
    owner, name = repo.split("/")[0], repo.split("/")[1]
    query = '{ repository(owner: "%s", name: "%s") { discussions(first: %d) { nodes { number title createdAt author { login } bodyText url } } } }' % (owner, name, min(max_results, 50))
    result = _graphql(query)
    if "error" in result:
        return f"(error: {result['error']})"
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