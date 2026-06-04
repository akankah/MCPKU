import uuid
import re
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sequential-thinking", instructions="""
Stuck-pattern detector for AI sessions. Lightweight: ~0ms latency per call.

USE: call think() whenever you make a decision in a non-trivial task. The tool
tracks your reasoning across the session and warns you if you start spinning
(retry/try/maybe patterns without progress) — at which point you MUST call
mcp_research.query() or websearch instead of trying the same approach again.

DO NOT use as a scratchpad for free-form thought (that's what your native
think_mode is for). Use think() only as a discipline signal: "I am about to
make decision X, please check if I'm stuck."

PARALLEL CALL OK: new_session/think/reset can run alongside other MCP tools
in the same tool batch (e.g., parallel([think(reasoning=...), research.query(q)])).
""")

# Session-isolated storage — tidak ada lagi global THOUGHTS yang shared
_sessions: dict[str, list[dict]] = {}


def _get_session(session_id: str) -> list[dict]:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


# Phrases that suggest the model is about to repeat the same failed approach
# without seeking external information. Matched case-insensitive.
_STUCK_PATTERNS = re.compile(
    r"\b(let me try|coba lagi|try again|maybe this will|workaround|"
    r"hopefully|perhaps|seharusnya|trying again|"
    r"let me attempt|mungkin|coba (pakai|ubah|cek) lagi)\b",
    re.IGNORECASE,
)

# Phrases that suggest progress (new info, search result, file read, fix verified)
_PROGRESS_PATTERNS = re.compile(
    r"\b(found|menemukan|fixed|working|search result|websearch said|"
    r"the doc says|menurut sumber|berdasarkan|fixed by|"
    r"solved|according to|docs?\s+confirm)\b",
    re.IGNORECASE,
)


def _detect_stuck(thoughts: list[dict]) -> tuple[bool, str]:
    """Return (is_stuck, hint_message).

    A session is 'stuck' when the last 2+ thoughts contain stuck-pattern
    phrases without any progress-pattern in between.
    """
    if len(thoughts) < 2:
        return (False, "")

    recent = thoughts[-3:]  # last 3 thoughts
    stuck_count = sum(1 for t in recent if _STUCK_PATTERNS.search(t["thought"]))
    progress_count = sum(1 for t in recent if _PROGRESS_PATTERNS.search(t["thought"]))

    if stuck_count >= 2 and progress_count == 0:
        return (
            True,
            "\n\n!!! AUTOFALLBACK TRIGGERED !!!\n"
            "You have repeated retry/try patterns in the last "
            f"{stuck_count} thoughts without progress. "
            "STOP. Call websearch('how to fix this specific problem') "
            "or webfetch(<error message URL>) BEFORE the next think().\n"
            "Skipping this wastes the user's time.",
        )
    return (False, "")


@mcp.tool(
    name="think",
    description=(
        "Rekam langkah pemikiran untuk reasoning bertahap. "
        "Gunakan session_id unik per task agar tidak tercampur antar sesi. "
        "Kosongkan session_id untuk auto-generate.\n\n"
        "AUTOFALLBACK: this tool tracks stuck patterns. If you record "
        "2+ retry/try thoughts without progress, it will REFUSE to "
        "continue and demand a websearch call first. Use that as your "
        "external signal that you are looping."
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

    is_stuck, stuck_hint = _detect_stuck(thoughts)
    history = "\n".join(f"Step {t['step']}: {t['thought']}" for t in thoughts)
    return (
        f"[session: {sid}] Thought recorded as step {step}.\n\n"
        f"Current thought chain:\n{history}"
        f"{stuck_hint}"
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
