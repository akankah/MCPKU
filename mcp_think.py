import uuid
import re
import time
from typing import Optional
from mcp.server.fastmcp import FastMCP

LAG_THRESHOLD_MS = 10_000  # > 10s between think() calls = LAG

mcp = FastMCP("sequential-thinking", instructions="""
Stuck-pattern detector for AI sessions. Lightweight: ~0ms latency per call.

USE: call think() whenever you make a decision in a non-trivial task. The tool
tracks your reasoning across the session and warns you if you start spinning
(retry/try/maybe patterns without progress) — at which point you MUST call
mcp_research.query() or websearch instead of trying the same approach again.

LAG DETECTION: pass lag_ms=<ms since last think()> on every call. If lag > 10s
AND no progress pattern in your last thought, this tool returns a hard
"PARALLEL WEB SEARCH" trigger — you MUST batch think() with web.search_web() +
web.search_stackoverflow() in ONE round-trip, not sequentially.

DO NOT use as a scratchpad for free-form thought (that's what your native
think_mode is for). Use think() only as a discipline signal: "I am about to
make decision X, please check if I'm stuck."

PARALLEL CALL OK: new_session/think/reset can run alongside other MCP tools
in the same tool batch (e.g., parallel([think(reasoning=...), research.query(q)])).
""")

# Session-isolated storage — tidak ada lagi global THOUGHTS yang shared
_sessions: dict[str, list[dict]] = {}
_session_last_at: dict[str, float] = {}


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


def _detect_lag(lag_ms: int, thoughts: list[dict]) -> tuple[bool, str]:
    """Return (is_lagging, hint_message).

    If lag > 10s AND last thought has no progress pattern → demand a
    PARALLEL web search batch (think + web.search_web + web.search_stackoverflow
    in one round-trip).
    """
    if lag_ms <= LAG_THRESHOLD_MS or not thoughts:
        return (False, "")

    last = thoughts[-1]["thought"]
    has_progress = bool(_PROGRESS_PATTERNS.search(last))
    if has_progress:
        return (False, "")

    threshold_s = LAG_THRESHOLD_MS // 1000
    return (
        True,
        f"\n\n!!! LAG DETECTED ({lag_ms / 1000:.1f}s > {threshold_s}s) !!!\n"
        "You spent too long on the last step without progress signal. "
        "STOP reasoning and run a PARALLEL web search batch in ONE round-trip:\n"
        "  parallel([\n"
        "    think(reasoning='searching for <error keyword>', lag_ms=0),\n"
        "    web.search_web('<error keyword> 2025 fix'),\n"
        "    web.search_stackoverflow('<error keyword>'),\n"
        "  ])\n"
        "Do NOT call them sequentially — that defeats the speed gain.",
    )


@mcp.tool(
    name="think",
    description=(
        "Rekam langkah pemikiran untuk reasoning bertahap. "
        "Gunakan session_id unik per task agar tidak tercampur antar sesi. "
        "Kosongkan session_id untuk auto-generate.\n\n"
        "AUTOFALLBACK: this tool tracks stuck patterns. If you record "
        "2+ retry/try thoughts without progress, it will REFUSE to "
        "continue and demand a websearch call first. Use that as your "
        "external signal that you are looping.\n\n"
        "LAG DETECTION: pass lag_ms=<ms since your last step> on every call. "
        f"If lag > {LAG_THRESHOLD_MS // 1000}s AND last thought has no progress "
        "pattern, returns a hard 'PARALLEL WEB SEARCH' trigger — you must "
        "batch think + web.search_web + web.search_stackoverflow in one round-trip."
    )
)
async def think(
    thought: str,
    step_number: int = 0,
    session_id: str = "",
    lag_ms: int = 0,
) -> str:
    if not thought.strip():
        return "(empty thought)"

    sid = session_id.strip() or "default"
    thoughts = _get_session(sid)
    now = time.monotonic()

    step = step_number if step_number > 0 else len(thoughts) + 1
    entry = {"step": step, "thought": thought.strip(), "at": now, "lag_ms": lag_ms}
    thoughts.append(entry)
    _session_last_at[sid] = now

    is_stuck, stuck_hint = _detect_stuck(thoughts)
    is_lag, lag_hint = _detect_lag(lag_ms, thoughts)
    history = "\n".join(f"Step {t['step']}: {t['thought']}" for t in thoughts)
    return (
        f"[session: {sid}] Thought recorded as step {step}.\n\n"
        f"Current thought chain:\n{history}"
        f"{stuck_hint}"
        f"{lag_hint}"
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
