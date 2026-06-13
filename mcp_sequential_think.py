"""
mcp_sequential_think.py — Sequential Thinking MCP Server
=========================================================
Structured step-by-step reasoning tool that breaks down complex problems,
supports revision, branching, and dynamic thought count adjustment.

References:
- Official: https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking
- NPM: @modelcontextprotocol/server-sequential-thinking
- Explainer: https://medium.com/@Micheal-Lanham/building-smarter-ai-agents-how-sequential-thinking-mcp-transforms-complex-problem-solving-443e68b4d487
"""

import json
import time
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sequential-thinking", instructions="""
Structured step-by-step reasoning tool.

Use sequential_thinking() to break down complex problems into
manageable steps. Each thought builds on previous ones. Supports:
- Revision: go back and refine a previous thought
- Branching: explore alternative reasoning paths
- Dynamic thought count: adjust total as understanding deepens

Call this repeatedly for each step of analysis. Set
nextThoughtNeeded=true to continue, false when done.
""")

# ── In-memory thought sessions ──────────────────────────────────────────────

_sessions: Dict[str, List[Dict]] = {}
_session_counter = 0


def _get_or_create_session(session_id: str = "") -> str:
    global _session_counter
    if not session_id:
        _session_counter += 1
        session_id = f"seq-think-{_session_counter}"
    if session_id not in _sessions:
        _sessions[session_id] = []
    return session_id


def _branch_id(session_id: str, branch_from: int) -> str:
    return f"{session_id}-br-{branch_from}-{int(time.time()*1000)%10000}"


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(name="sequential_thinking",
          description="Facilitates a detailed, step-by-step thinking process for problem-solving and analysis.")
async def sequential_thinking(
    thought: str,
    next_thought_needed: bool,
    thought_number: int,
    total_thoughts: int,
    session_id: str = "",
    is_revision: bool = False,
    revises_thought: int = 0,
    branch_from_thought: int = 0,
    branch_id: str = "",
    needs_more_context: bool = False,
    next_thought_branch: str = "",
) -> str:
    sid = _get_or_create_session(session_id)
    now = time.time()
    branch_id_effective = branch_id
    if branch_from_thought > 0 and not branch_id:
        branch_id_effective = _branch_id(sid, branch_from_thought)

    entry = {
        "thought_number": thought_number,
        "thought": thought,
        "total_thoughts": total_thoughts,
        "next_thought_needed": next_thought_needed,
        "is_revision": is_revision,
        "revises_thought": revises_thought if is_revision else None,
        "branch_from_thought": branch_from_thought if branch_from_thought > 0 else None,
        "branch_id": branch_id_effective if (branch_from_thought > 0 or branch_id) else None,
        "needs_more_context": needs_more_context,
        "next_thought_branch": next_thought_branch if next_thought_branch else None,
        "timestamp": now,
        "formatted_time": time.strftime("%H:%M:%S", time.localtime(now)),
    }

    # Look up revision target
    revision_info = None
    if is_revision and revises_thought > 0:
        for t in _sessions[sid]:
            if t["thought_number"] == revises_thought:
                revision_info = {
                    "original_thought": t["thought"],
                    "original_branch": t.get("branch_id"),
                }
                t["revised_by"] = thought_number
                break
        if revision_info:
            entry["revision_of"] = revision_info
        else:
            entry["revision_of"] = {"error": f"Thought #{revises_thought} not found"}

    # Look up branch origin
    if branch_from_thought > 0:
        for t in _sessions[sid]:
            if t["thought_number"] == branch_from_thought:
                entry["branch_origin"] = {
                    "thought": t["thought"][:100] + "..." if len(t["thought"]) > 100 else t["thought"],
                }
                break

    _sessions[sid].append(entry)

    # Build thought history
    history = [{
        "thought_number": t["thought_number"],
        "thought": t["thought"][:200] + ("..." if len(t["thought"]) > 200 else ""),
        "is_revision": t.get("is_revision", False),
        "branch_id": t.get("branch_id"),
        "formatted_time": t.get("formatted_time", ""),
    } for t in _sessions[sid]]

    return json.dumps({
        "session_id": sid,
        "thought_number": thought_number,
        "total_thoughts": total_thoughts,
        "next_thought_needed": next_thought_needed,
        "thought_count": len(_sessions[sid]),
        "branches": list(set(
            t.get("branch_id") for t in _sessions[sid] if t.get("branch_id")
        )),
        "revision_of": revision_info,
        "history_length": len(history),
        "history": history,
    }, ensure_ascii=False)


@mcp.tool(name="get_thought_history",
          description="Retrieve the full thought history for a session.")
async def get_thought_history(session_id: str) -> str:
    if session_id not in _sessions or not _sessions[session_id]:
        return json.dumps({"error": f"Session not found: {session_id}"}, ensure_ascii=False)

    thoughts = _sessions[session_id]
    branches = set()
    for t in thoughts:
        bid = t.get("branch_id")
        if bid:
            branches.add(bid)

    return json.dumps({
        "session_id": session_id,
        "total_thoughts": len(thoughts),
        "current_branches": list(branches),
        "thoughts": thoughts,
    }, ensure_ascii=False)


@mcp.tool(name="think_summary",
          description="Get a concise summary of the thinking process for a session.")
async def think_summary(session_id: str) -> str:
    if session_id not in _sessions or not _sessions[session_id]:
        return json.dumps({"error": f"Session not found: {session_id}"}, ensure_ascii=False)

    thoughts = _sessions[session_id]
    main_chain = [t for t in thoughts if not t.get("branch_id")]
    branches = {}
    for t in thoughts:
        bid = t.get("branch_id")
        if bid:
            branches.setdefault(bid, []).append(t)

    return json.dumps({
        "session_id": session_id,
        "total_thoughts": len(thoughts),
        "main_chain_count": len(main_chain),
        "branches_count": len(branches),
        "branch_details": {bid: len(ts) for bid, ts in branches.items()},
        "first_thought": main_chain[0]["thought"][:100] + "..." if main_chain else "",
        "last_thought": thoughts[-1]["thought"][:100] + "..." if thoughts else "",
        "revisions_made": sum(1 for t in thoughts if t.get("is_revision")),
        "duration_sec": round(thoughts[-1]["timestamp"] - thoughts[0]["timestamp"], 1) if len(thoughts) > 1 else 0,
    }, ensure_ascii=False)


@mcp.tool(name="clear_session",
          description="Clear a thinking session or all sessions.")
async def clear_session(session_id: str = "") -> str:
    if session_id:
        if session_id in _sessions:
            del _sessions[session_id]
            return json.dumps({"cleared": session_id}, ensure_ascii=False)
        return json.dumps({"error": f"Session not found: {session_id}"}, ensure_ascii=False)
    else:
        count = len(_sessions)
        _sessions.clear()
        return json.dumps({"cleared_all": True, "session_count": count}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
