from ._client import GITHUB_TOKEN, API_BASE, _headers, _api, _get, _post, _patch, _put, _delete, _format_repo, _graphql
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("github", instructions="""
GitHub API tools. Search repos, read files, manage issues, PRs, releases, gists,
discussions, notifications, organizations, labels, actions workflows, and more.
Requires GITHUB_API_KEY environment variable.
""")

from . import repos, issues, labels, pulls, releases, gists, notifications, orgs, branches, workflows, discussions