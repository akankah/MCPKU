import os, logging
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import git
from git.exc import BadName, GitCommandError

DEFAULT_CONTEXT_LINES = 3
MAX_DIFF_LENGTH = 50000

mcp = FastMCP("git", instructions="""
Git repository management: status, diff, commit, add, reset, log, branches,
checkout, show, stash, merge, rebase, clone, tag, blame, clean.
All tools require a repo_path parameter pointing to a valid Git repository.
""")

def _reject_flag(value: str, name: str):
    if value and value.startswith("-"):
        raise BadName(f"Invalid {name}: '{value}' - cannot start with '-'")

def _get_repo(repo_path: str) -> git.Repo:
    return git.Repo(repo_path)

def _trim_diff(diff: str, max_len: int = MAX_DIFF_LENGTH) -> str:
    if len(diff) > max_len:
        return diff[:max_len] + f"\n\n[...diff truncated at {max_len} chars]"
    return diff

@mcp.tool(
    name="git_status",
    description="Shows the working tree status."
)
async def git_status(repo_path: str) -> str:
    repo = _get_repo(repo_path)
    status = repo.git.status()
    branch = repo.active_branch.name
    return f"Branch: {branch}\n\n{status}"

@mcp.tool(
    name="git_diff_unstaged",
    description="Shows changes in working directory not yet staged."
)
async def git_diff_unstaged(repo_path: str, context_lines: int = DEFAULT_CONTEXT_LINES) -> str:
    repo = _get_repo(repo_path)
    diff = repo.git.diff(f"--unified={context_lines}")
    return f"Unstaged changes:\n{_trim_diff(diff)}"

@mcp.tool(
    name="git_diff_staged",
    description="Shows changes that are staged for commit."
)
async def git_diff_staged(repo_path: str, context_lines: int = DEFAULT_CONTEXT_LINES) -> str:
    repo = _get_repo(repo_path)
    diff = repo.git.diff(f"--unified={context_lines}", "--cached")
    return f"Staged changes:\n{_trim_diff(diff)}"

@mcp.tool(
    name="git_diff",
    description="Shows differences between branches or commits."
)
async def git_diff(repo_path: str, target: str, context_lines: int = DEFAULT_CONTEXT_LINES) -> str:
    _reject_flag(target, "target")
    repo = _get_repo(repo_path)
    repo.rev_parse(target)
    diff = repo.git.diff(f"--unified={context_lines}", target)
    return f"Diff with {target}:\n{_trim_diff(diff)}"

@mcp.tool(
    name="git_commit",
    description="Records changes to the repository."
)
async def git_commit(repo_path: str, message: str, all: bool = False) -> str:
    repo = _get_repo(repo_path)
    if all:
        repo.git.add(".")
    commit = repo.index.commit(message)
    return f"Changes committed successfully with hash {commit.hexsha}"

@mcp.tool(
    name="git_add",
    description="Adds file contents to the staging area."
)
async def git_add(repo_path: str, files: list) -> str:
    repo = _get_repo(repo_path)
    if files == ["."]:
        repo.git.add(".")
    else:
        repo.git.add("--", *files)
    return "Files staged successfully"

@mcp.tool(
    name="git_reset",
    description="Unstages staged changes. Use mode=hard to discard working directory changes too."
)
async def git_reset(repo_path: str, mode: str = "mixed", target: str = "HEAD") -> str:
    _reject_flag(target, "target")
    repo = _get_repo(repo_path)
    if mode == "soft":
        repo.git.reset("--soft", target)
    elif mode == "hard":
        repo.git.reset("--hard", target)
    else:
        repo.git.reset(target)
    return f"Reset {mode} to {target}"

@mcp.tool(
    name="git_log",
    description="Shows the commit logs with optional filtering."
)
async def git_log(repo_path: str, max_count: int = 10, start_timestamp: str = None, end_timestamp: str = None, branch: str = None, author: str = None) -> str:
    _reject_flag(start_timestamp or "", "start_timestamp")
    _reject_flag(end_timestamp or "", "end_timestamp")
    repo = _get_repo(repo_path)

    args = [f"--max-count={max_count}", "--format=%H|%an|%ae|%ad|%s", "--date=iso"]
    if start_timestamp: args.extend(["--since", start_timestamp])
    if end_timestamp: args.extend(["--until", end_timestamp])
    if branch: args.append(branch)
    if author: args.extend(["--author", author])

    log_output = repo.git.log(*args)
    if not log_output.strip():
        return "(no commits found)"
    lines = []
    for entry in log_output.split("\n"):
        parts = entry.split("|", 4)
        if len(parts) >= 5:
            lines.append(f"  {parts[0][:8]} {parts[4]} ({parts[1]}, {parts[3]})")
        elif parts:
            lines.append(f"  {entry}")
    return f"Commit history ({max_count}):\n" + "\n".join(lines)

@mcp.tool(
    name="git_create_branch",
    description="Creates a new branch from an optional base branch or commit."
)
async def git_create_branch(repo_path: str, branch_name: str, base_branch: str = None) -> str:
    _reject_flag(branch_name, "branch_name")
    _reject_flag(base_branch or "", "base_branch")
    repo = _get_repo(repo_path)
    if base_branch:
        base = repo.references[base_branch]
    else:
        base = repo.active_branch
    repo.create_head(branch_name, base)
    return f"Created branch '{branch_name}' from '{base.name}'"

@mcp.tool(
    name="git_checkout",
    description="Switches branches or restores working tree files."
)
async def git_checkout(repo_path: str, branch_name: str, create: bool = False) -> str:
    _reject_flag(branch_name, "branch_name")
    repo = _get_repo(repo_path)
    if create:
        repo.git.checkout("-b", branch_name)
        return f"Created and switched to branch '{branch_name}'"
    repo.rev_parse(branch_name)
    repo.git.checkout(branch_name)
    return f"Switched to branch '{branch_name}'"

@mcp.tool(
    name="git_show",
    description="Shows the contents of a commit with diff."
)
async def git_show(repo_path: str, revision: str) -> str:
    _reject_flag(revision, "revision")
    repo = _get_repo(repo_path)
    commit = repo.commit(revision)
    output = [
        f"Commit: {commit.hexsha}",
        f"Author: {commit.author!r}",
        f"Date: {commit.authored_datetime}",
        f"Message: {commit.message.strip()}"
    ]
    if commit.parents:
        parent = commit.parents[0]
        diff = parent.diff(commit, create_patch=True)
    else:
        diff = commit.diff(git.NULL_TREE, create_patch=True)
    for d in diff:
        output.append(f"\n--- {d.a_path}\n+++ {d.b_path}")
        if d.diff:
            decoded = d.diff.decode("utf-8") if isinstance(d.diff, bytes) else d.diff
            output.append(decoded)
    result = "\n".join(output)
    return _trim_diff(result)

@mcp.tool(
    name="git_branch",
    description="List Git branches (local, remote, or all) with optional filtering."
)
async def git_branch(repo_path: str, branch_type: str = "local", contains: str = None, not_contains: str = None) -> str:
    _reject_flag(contains or "", "contains")
    _reject_flag(not_contains or "", "not_contains")
    repo = _get_repo(repo_path)
    args = []
    match branch_type:
        case "local": pass
        case "remote": args.append("-r")
        case "all": args.append("-a")
        case _: return f"Invalid branch type: {branch_type}"
    if contains: args.extend(["--contains", contains])
    if not_contains: args.extend(["--no-contains", not_contains])
    result = repo.git.branch(*args)
    return f"Branches ({branch_type}):\n{result}"

# ── New tools beyond official ────────────────────────────────────────────

@mcp.tool(
    name="git_stash",
    description="Stash changes in working directory. pop=True to restore latest stash."
)
async def git_stash(repo_path: str, action: str = "push", message: str = None) -> str:
    repo = _get_repo(repo_path)
    match action:
        case "push":
            args = ["push"]
            if message: args.extend(["-m", message])
            repo.git.stash(*args)
            return "Changes stashed"
        case "pop":
            repo.git.stash("pop")
            return "Latest stash applied and removed"
        case "apply":
            repo.git.stash("apply")
            return "Latest stash applied (kept in stash)"
        case "drop":
            repo.git.stash("drop")
            return "Latest stash dropped"
        case "list":
            result = repo.git.stash("list")
            return result if result.strip() else "(no stashes)"
        case _:
            return f"Unknown action: {action}"

@mcp.tool(
    name="git_merge",
    description="Merge a branch into the current branch."
)
async def git_merge(repo_path: str, branch: str, ff_only: bool = False, squash: bool = False) -> str:
    _reject_flag(branch, "branch")
    repo = _get_repo(repo_path)
    args = [branch]
    if ff_only: args.insert(0, "--ff-only")
    if squash: args.insert(0, "--squash")
    try:
        repo.git.merge(*args)
        return f"Merged '{branch}' into '{repo.active_branch.name}'"
    except GitCommandError as e:
        return f"(merge conflict: {e.stderr[:300] if e.stderr else str(e)})"

@mcp.tool(
    name="git_rebase",
    description="Rebase current branch onto another branch."
)
async def git_rebase(repo_path: str, onto: str, interactive: bool = False) -> str:
    _reject_flag(onto, "onto")
    repo = _get_repo(repo_path)
    try:
        if interactive:
            repo.git.rebase("-i", onto)
        else:
            repo.git.rebase(onto)
        return f"Rebased onto '{onto}'"
    except GitCommandError as e:
        return f"(rebase conflict: {e.stderr[:300] if e.stderr else str(e)})"

@mcp.tool(
    name="git_clone",
    description="Clone a repository into a local directory."
)
async def git_clone(url: str, dest_path: str, branch: str = None, depth: int = None) -> str:
    args = [url, dest_path]
    if branch: args.extend(["--branch", branch])
    if depth: args.extend(["--depth", str(depth)])
    try:
        git.Repo.clone_from(url, dest_path, branch=branch, depth=depth)
        return f"Cloned {url} to {dest_path}"
    except GitCommandError as e:
        return f"(clone failed: {e.stderr[:300] if e.stderr else str(e)})"

@mcp.tool(
    name="git_tag",
    description="List, create, or delete tags."
)
async def git_tag(repo_path: str, action: str = "list", tag_name: str = None, message: str = None) -> str:
    repo = _get_repo(repo_path)
    match action:
        case "list":
            tags = repo.git.tag()
            return tags if tags.strip() else "(no tags)"
        case "create":
            if not tag_name: return "(tag_name required)"
            repo.git.tag(tag_name, "-m" if message else None, message or None)
            return f"Tag '{tag_name}' created"
        case "delete":
            if not tag_name: return "(tag_name required)"
            repo.git.tag("-d", tag_name)
            return f"Tag '{tag_name}' deleted"
        case _:
            return f"Unknown action: {action}"

@mcp.tool(
    name="git_blame",
    description="Show what revision and author last modified each line of a file."
)
async def git_blame(repo_path: str, file_path: str) -> str:
    repo = _get_repo(repo_path)
    try:
        result = repo.git.blame(file_path)
        if len(result) > 10000:
            result = result[:10000] + "\n\n[...truncated]"
        return result
    except GitCommandError as e:
        return f"(error: {e.stderr[:200] if e.stderr else str(e)})"

if __name__ == "__main__":
    mcp.run(transport="stdio")
