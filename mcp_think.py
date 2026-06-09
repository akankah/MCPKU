"""
mcp_think.py — MCPKU Cognitive Runtime Layer
============================================
Anti-loop, anti-delusion reasoning monitor for AI agents.

Tracks reasoning sessions, detects stuck patterns (semantic + regex),
scores progress, auto-triggers search when looping, and persists
sessions for continuity across restarts.

Architecture:
  think() → record thought + detect stuck + score progress + check lag
             ↓                        ↓
          session history          auto-trigger suggestions
          (memory + persistent)    (web search / tool switch)
"""

import json
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

LAG_THRESHOLD_MS = 10_000
_SESSIONS_DIR = Path(__import__("os").environ.get("TEMP", "/tmp")) / "mcpku" / "think_sessions"
_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("sequential-thinking", instructions="""
Cognitive monitor for AI sessions. Detects stuck patterns, scores progress,
and forces external search when looping.

USE: call think() on every non-trivial decision. The tool tracks reasoning
across the session and warns if you start spinning. On WARNING level,
you MUST call websearch or research before the next think().

On CRITICAL level, the tool auto-suggests a search query based on
the last failure context.
""")


# ── Session: persistent + in-memory ─────────────────────────────────────────

_sessions: dict[str, list[dict]] = {}


def _session_path(sid: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", sid)
    return _SESSIONS_DIR / f"{safe}.jsonl"


def _load_session(sid: str) -> list[dict]:
    if sid in _sessions:
        return _sessions[sid]
    path = _session_path(sid)
    thoughts = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        thoughts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    _sessions[sid] = thoughts
    return thoughts


def _save_thought(sid: str, entry: dict):
    path = _session_path(sid)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if sid in _sessions:
        _sessions[sid].append(entry)


def _clear_session(sid: str):
    _sessions.pop(sid, None)
    path = _session_path(sid)
    if path.exists():
        path.unlink()


# ── Semantic repetition detection ────────────────────────────────────────────

def _char_ngrams(text: str, n: int = 4) -> set[str]:
    """Character n-grams for similarity comparison."""
    text = text.lower()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _text_similarity(a: str, b: str) -> float:
    """Jaccard similarity on character 4-grams."""
    if not a or not b:
        return 0.0
    ngrams_a = _char_ngrams(a)
    ngrams_b = _char_ngrams(b)
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = ngrams_a & ngrams_b
    union = ngrams_a | ngrams_b
    return len(intersection) / len(union)


def _detect_repetition(thoughts: list[dict]) -> tuple[bool, float]:
    """Detect semantic repetition in recent thoughts using n-gram overlap."""
    if len(thoughts) < 2:
        return (False, 0.0)
    recent = thoughts[-3:]
    pairs = [(recent[i]["thought"], recent[j]["thought"])
             for i in range(len(recent))
             for j in range(i + 1, len(recent))]
    if not pairs:
        return (False, 0.0)
    max_sim = max(_text_similarity(a, b) for a, b in pairs)
    return (max_sim > 0.75, max_sim)


# ── Progress scoring ─────────────────────────────────────────────────────────

# Phrases suggesting stuck (same as before, weighted)
_STUCK_KEYWORDS = re.compile(
    r"\b(let me try|coba lagi|try again|maybe this will|workaround|"
    r"hopefully|perhaps|seharusnya|trying again|"
    r"let me attempt|mungkin|coba (pakai|ubah|cek) lagi)\b",
    re.IGNORECASE,
)

# Phrases suggesting progress (external grounding, new info)
_PROGRESS_KEYWORDS = re.compile(
    r"\b(found|menemukan|fixed|working|search result|websearch said|"
    r"the doc says|menurut sumber|berdasarkan|fixed by|"
    r"solved|according to|docs?\s+confirm|research says|"
    r"found that|ternyata|setelah|maka|sehingga)\b",
    re.IGNORECASE,
)


def _score_progress(thought: str, previous_thoughts: list[dict]) -> float:
    """Score a thought on 0.0 (stuck) to 1.0 (making progress)."""
    score = 0.5  # neutral

    # +0.3 for progress keywords
    if _PROGRESS_KEYWORDS.search(thought):
        score += 0.3

    # -0.3 for stuck keywords
    if _STUCK_KEYWORDS.search(thought):
        score -= 0.3

    # +0.2 if this thought references external sources (URLs, file paths, code)
    if re.search(r'https?://|/[a-zA-Z]:[\\/]|\.py|\.js|\.tsx?|`[^`]+`', thought):
        score += 0.2

    # -0.1 per 100 chars of vague text (no concrete nouns)
    nouns = len(re.findall(r'\b[A-Z][a-z]{2,}\b', thought))
    if nouns < 3 and len(thought) > 100:
        score -= 0.1

    # -0.2 if highly similar to last thought (semantic repetition)
    if previous_thoughts:
        last = previous_thoughts[-1]["thought"]
        sim = _text_similarity(thought, last)
        if sim > 0.7:
            score -= 0.2 * sim

    return max(0.0, min(1.0, score))


# ── State connector: check workflow_state.jsonl ─────────────────────────────

def _check_workflow_failures(workflow_dir: str = "") -> tuple[int, str]:
    """Check how many consecutive failures in workflow state."""
    if not workflow_dir:
        return (0, "")
    state_file = Path(workflow_dir) / "workflow_state.jsonl"
    if not state_file.exists():
        return (0, "")
    failures = 0
    last_error = ""
    with open(state_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("status") == "failed":
                    failures += 1
                    last_error = entry.get("error_info", "")
                elif entry.get("status") == "completed":
                    failures = 0
            except json.JSONDecodeError:
                pass
    return (failures, last_error[:200])


# ── Stuck + lag detection (enhanced) ─────────────────────────────────────────

def _detect_stuck(thoughts: list[dict], workflow_dir: str = "") -> tuple[str, str]:
    """
    Return (severity, message).
    severity: "" | "INFO" | "WARNING" | "CRITICAL" | "ABORT"
    """
    if len(thoughts) < 2:
        return ("", "")

    recent = thoughts[-3:]
    progress_scores = [_score_progress(t["thought"], thoughts[:i])
                       for i, t in enumerate(recent)]

    avg_score = round(sum(progress_scores) / len(progress_scores), 6)
    is_rep, rep_sim = _detect_repetition(thoughts)

    # Detect stuck as consecutive stuck-only thoughts (no progress keywords) without interleaved progress
    consecutive_stuck = 0
    has_recent_progress = False
    for t in reversed(recent):
        has_stuck = bool(_STUCK_KEYWORDS.search(t["thought"]))
        has_progress = bool(_PROGRESS_KEYWORDS.search(t["thought"]))
        if has_progress:
            has_recent_progress = True
            if has_stuck:
                continue
            break
        if has_stuck:
            consecutive_stuck += 1
        else:
            break

    wf_failures, wf_error = _check_workflow_failures(workflow_dir)

    context = []
    if wf_failures >= 2:
        context.append(f"workflow: {wf_failures} consecutive failures")
    if is_rep:
        context.append(f"semantic repetition: {rep_sim:.0%} similarity")

    context_str = " | ".join(context) if context else ""

    # CRITICAL: consecutive stuck thoughts, no recent progress
    if consecutive_stuck >= 2 and not has_recent_progress:
        search_hint = _suggest_search(thoughts)
        return ("CRITICAL",
                f"\n\n!!! CRITICAL: STUCK ({context_str}) !!!\n"
                f"Progress score: {avg_score:.2f}/1.0 | Consecutive stuck: {consecutive_stuck}\n"
                f"Auto-suggested: {search_hint}")

    # WARNING: low score + repetition or workflow failures or stuck pattern
    if avg_score < 0.4 and (wf_failures >= 1 or is_rep or consecutive_stuck >= 1):
        search_hint = _suggest_search(thoughts)
        return ("WARNING",
                f"\n\n!!! WARNING: Possible loop ({context_str}) !!!\n"
                f"Progress score: {avg_score:.2f}/1.0\n"
                f"Call websearch before next step.\n"
                f"Suggested: {search_hint}")

    # INFO: low score
    if avg_score < 0.35:
        return ("INFO",
                f"\n[think] Progress score low ({avg_score:.2f}). "
                "Consider searching for external info.")

    return ("", "")


def _detect_lag(lag_ms: int, thoughts: list[dict]) -> str:
    """Return hint message or empty."""
    if lag_ms <= LAG_THRESHOLD_MS or not thoughts:
        return ""

    last = thoughts[-1]["thought"]
    score = _score_progress(last, thoughts[:-1])
    if score >= 0.5:
        return ""

    threshold_s = LAG_THRESHOLD_MS // 1000
    return (
        f"\n\n!!! LAG DETECTED ({lag_ms / 1000:.1f}s > {threshold_s}s) !!!\n"
        "Stop reasoning. Run a PARALLEL web search batch:\n"
        "  parallel([think(...), web.search_web('<query>'), web.search_stackoverflow('<query>')])\n"
    )


def _suggest_search(thoughts: list[dict]) -> str:
    """Extract a search query from the last failure context."""
    if not thoughts:
        return "search for error/solution"
    last = thoughts[-1]["thought"]
    # Extract key technical terms
    terms = re.findall(r'\b([A-Za-z][A-Za-z0-9_]{2,}(?:Error|Exception|Failed|not found|timeout))\b', last)
    if terms:
        return f"websearch('{terms[0]} fix solution')"
    # Extract quoted strings
    quotes = re.findall(r'"([^"]{10,})"', last)
    if quotes:
        return f"websearch('{quotes[0][:60]}')"
    # Fallback: last 60 chars of thought
    snippet = last.strip()[-60:]
    return f"websearch('{snippet}')"


# ── MCP Tools ────────────────────────────────────────────────────────────────

@mcp.tool(
    name="think",
    description=(
        "Record a reasoning step with stuck detection + progress scoring + lag monitoring. "
        "Severity levels: INFO (low progress), WARNING (possible loop), CRITICAL (stuck, must search). "
        "On CRITICAL, an auto-suggested search query is returned."
    )
)
async def think(
    thought: str,
    step_number: int = 0,
    session_id: str = "",
    lag_ms: int = 0,
    workflow_dir: str = "",
) -> str:
    """
    Record a reasoning step.

    Args:
        thought: The reasoning text.
        step_number: Optional explicit step number.
        session_id: Unique session ID (auto-generate with new_session).
        lag_ms: Milliseconds since last think() call.
        workflow_dir: Optional path to workflow dir for state cross-reference.
    """
    if not thought.strip():
        return '(empty thought)'

    sid = session_id.strip() or "default"
    thoughts = _load_session(sid)
    now = time.monotonic()
    step = step_number if step_number > 0 else len(thoughts) + 1

    score = _score_progress(thought, thoughts)
    entry = {
        "step": step,
        "thought": thought.strip(),
        "at": now,
        "lag_ms": lag_ms,
        "progress_score": round(score, 3),
    }
    _save_thought(sid, entry)

    stuck_severity, stuck_msg = _detect_stuck(thoughts + [entry], workflow_dir)
    lag_msg = _detect_lag(lag_ms, thoughts)

    history = "\n".join(
        f"Step {t['step']} ({t.get('progress_score', '?'):.2f}): {t['thought'][:100]}"
        for t in thoughts[-5:]
    )

    return (
        f"[session: {sid}] Step {step} | Progress: {score:.2f}/1.0\n\n"
        f"Recent:\n{history}"
        f"{stuck_msg}"
        f"{lag_msg}"
    )


@mcp.tool(
    name="think_status",
    description="Get session summary: progress trend, repetition risk, step count."
)
async def think_status(session_id: str = "") -> str:
    """Get session summary with progress analytics."""
    sid = session_id.strip() or "default"
    thoughts = _load_session(sid)
    if not thoughts:
        return f"[session: {sid}] No thoughts recorded."

    scores = [t.get("progress_score", 0.5) for t in thoughts]
    avg_score = sum(scores) / len(scores)
    trend = "improving" if len(scores) >= 2 and scores[-1] > scores[0] else "declining" if len(scores) >= 2 else "neutral"
    rep, rep_sim = _detect_repetition(thoughts)

    return json.dumps({
        "session": sid,
        "steps": len(thoughts),
        "avg_progress": round(avg_score, 2),
        "trend": trend,
        "repetition_risk": round(rep_sim, 2) if rep else 0,
        "last_thought": thoughts[-1]["thought"][:100],
        "persistent": str(_session_path(sid)),
    }, indent=2, ensure_ascii=False)


@mcp.tool(
    name="reset_thinking",
    description="Reset thought chain for a session. Clears both memory and persistent storage."
)
async def reset_thinking(session_id: str = "") -> str:
    sid = session_id.strip() or "default"
    _clear_session(sid)
    return f"[session: {sid}] Thought chain reset (persistent + memory)."


@mcp.tool(
    name="new_session",
    description="Create a new isolated session with persistent storage."
)
async def new_session() -> str:
    sid = str(uuid.uuid4())[:8]
    _load_session(sid)  # initialize empty
    return f"New session created: {sid} (persistent: {_session_path(sid)})"


@mcp.tool(
    name="think_search",
    description="Get an auto-suggested search query based on recent stuck context."
)
async def think_search(session_id: str = "") -> str:
    """Analyze recent thoughts and suggest a search query."""
    sid = session_id.strip() or "default"
    thoughts = _load_session(sid)
    if not thoughts:
        return "(no thoughts to analyze)"
    query = _suggest_search(thoughts)
    return f"Suggested search: {query}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
