import uuid
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sequential-thinking", instructions="""
Sequential thinking tool for structured reasoning.
Use when you need to break down complex problems step by step.
Each call records a thought step. Use session_id untuk isolasi antar sesi.
""")

# Session-isolated storage — tidak ada lagi global THOUGHTS yang shared
_sessions: dict[str, list[dict]] = {}


def _get_session(session_id: str) -> list[dict]:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


@mcp.tool(
    name="think",
    description=(
        "Rekam langkah pemikiran untuk reasoning bertahap. "
        "Gunakan session_id unik per task agar tidak tercampur antar sesi. "
        "Kosongkan session_id untuk auto-generate."
    )
)
async def think(
    thought: str,
    step_number: int = 0,
    session_id: str = "",
) -> str:
    if not thought.strip():
        return "(empty thought)"

    sid = session_id.strip() or "default"
    thoughts = _get_session(sid)

    step = step_number if step_number > 0 else len(thoughts) + 1
    entry = {"step": step, "thought": thought.strip()}
    thoughts.append(entry)

    history = "\n".join(f"Step {t['step']}: {t['thought']}" for t in thoughts)
    return (
        f"[session: {sid}] Thought recorded as step {step}.\n\n"
        f"Current thought chain:\n{history}"
    )


@mcp.tool(
    name="reset_thinking",
    description="Reset rantai pemikiran untuk session tertentu. Kosongkan session_id untuk reset 'default'."
)
async def reset_thinking(session_id: str = "") -> str:
    sid = session_id.strip() or "default"
    if sid in _sessions:
        _sessions.pop(sid)
    return f"[session: {sid}] Thought chain reset."


@mcp.tool(
    name="new_session",
    description="Buat session ID baru yang unik untuk memulai thought chain yang terisolasi."
)
async def new_session() -> str:
    sid = str(uuid.uuid4())[:8]
    _sessions[sid] = []
    return f"New session created: {sid}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
