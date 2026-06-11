import os
import subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("git_doc", instructions="""
Git Documentation Server: Auto-generate commit messages and PR summaries based on git diffs.
""")

def _get_diff(repo_path: str) -> str:
    try:
        # Get staged changes
        result = subprocess.run(
            ["git", "diff", "--staged"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except Exception as e:
        return f"Error getting diff: {str(e)}"

@mcp.tool(name="generate_commit_proposal", description="Analyze staged changes and propose a commit message.")
async def generate_commit_proposal(repo_path: str) -> str:
    """Analyzes git diff and returns a structured summary for commit/PR."""
    diff = _get_diff(repo_path)
    if not diff.strip():
        return "No staged changes found. Please 'git add' files first."
    
    # We return the diff so the AI agent (me) can reason over it and generate the message
    return f"STAGED CHANGES IN {repo_path}:\\n\\n{diff[:5000]}\\n\\n(Diff truncated if too long)"

@mcp.tool(name="generate_pr_summary", description="Generate a detailed PR summary for all commits between current branch and base.")
async def generate_pr_summary(repo_path: str, base_branch: str = "main") -> str:
    """Analyzes changes between current branch and base for PR description."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{base_branch}...HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        diff = result.stdout
        return f"FULL CHANGES FOR PR:\\n\\n{diff[:8000]}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
