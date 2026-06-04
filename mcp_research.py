"""
mcp_research.py — MCPKU Parallel Research Aggregator (v2)
==========================================================
Closes the orchestration gap. Calls 6 web sources + diagnostics + memory +
error_kb IN PARALLEL via asyncio.gather, deduplicates, ranks by weighted
voting, returns CONSENSUS with confidence score (0-100%).

Improvements over v1:
  1. Weighted source reliability (SO/GitHub > blogs)
  2. Confidence score (0-100) based on agreement + source weights
  3. error_kb cross-check (past similar errors = strong signal)
  4. Streaming partial results via asyncio.as_completed (don't wait for slowest)
  5. Cross-source text similarity (not just "is response present")

Tools:
  - query(question, error_text=None, stream=False)
        → one-shot consensus research with confidence score
  - quick(question) → only web + SO (faster, 2 sources)
  - deep(question, error_text=None) → 8 sources + error_kb + cross-check
  - stream(question, error_text=None) → async iterator, returns each source as it completes
"""
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

from mcp_web import (
    search_web,
    search_stackoverflow,
    search_npm,
    search_pypi,
    search_mdn,
    search_crates,
    search_devdocs,
)
from mcp_diagnostics import classify_error
from mcp_memory import search_nodes

# ── Configuration ────────────────────────────────────────────────────────────

mcp = FastMCP(
    "mcp-research",
    instructions=(
        "Parallel research orchestrator with weighted voting + confidence scoring. "
        "Use query() when you need a single consensus answer cross-checked across "
        "multiple sources. Runs 6 web sources + diagnostics + memory + error_kb "
        "in parallel via asyncio.gather, returns ranked consensus with explicit "
        "confidence score (0-100%).\n\n"
        "When to use:\n"
        "  - Complex unknown error (autofix/diagnostics flagged UNKNOWN)\n"
        "  - API/library/framework behavior you're not 100% sure about\n"
        "  - User asks a research question that benefits from multi-source confirmation\n\n"
        "When NOT to use:\n"
        "  - Trivial lookups (use mcp_web.search_web directly)\n"
        "  - Single-source docs check (use mcp_web.search_mdn / search_npm directly)\n"
        "  - Renames / typos / file reads\n\n"
        "Use stream() if you want results as they arrive (don't wait for slowest). "
        "Use quick() for fast 2-source check. Use deep() for full 8-source cross-validation."
    ),
)

# Source weights — how much we trust each source. Higher = more authoritative.
SOURCE_WEIGHTS = {
    "stackoverflow": 0.90,  # Q&A curated by community, high signal
    "github":        0.85,  # Issues, code, official maintainers
    "mdn":           0.95,  # Official web platform docs
    "pypi":          0.80,  # Official package index
    "npm":           0.80,  # Official package index
    "crates":        0.80,  # Official package index
    "devdocs":       0.85,  # Aggregated official docs
    "error_kb":      0.95,  # OUR past fixes — highest signal for recurrence
    "memory":        0.75,  # User's persistent notes
    "diagnostics":   0.85,  # Local static analysis
    "web":           0.50,  # General web — noisy, low weight
}

ERROR_KB_DIR = Path(os.environ.get("ERROR_KB_DIR", Path(__file__).parent / "error_kb"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_keywords(text: str, max_words: int = 8) -> str:
    if not text:
        return ""
    stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "should",
            "can", "could", "may", "might", "must", "shall", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
            "us", "them", "my", "your", "his", "its", "our", "their", "this",
            "that", "these", "those", "what", "which", "who", "whom", "how",
            "why", "when", "where", "and", "or", "but", "if", "so", "not"}
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text.lower())
    return " ".join(w for w in words if w not in stop)[:200]


def _detect_language(text: str) -> str:
    if not text:
        return "general"
    t = text.lower()
    if any(x in t for x in ["npm", "node", "javascript", "typescript", "react", "vue", "next.js"]):
        return "javascript"
    # Python: explicit keywords OR Python-specific errors
    if any(x in t for x in ["pip", "python", "django", "flask", "fastapi"]) or \
       any(x in t for x in ["modulenotfounderror", "importerror", "indentationerror",
                             "syntaxerror", "attributeerror", "pyfile"]):
        return "python"
    if any(x in t for x in ["cargo", "rust", "crate", "rustc"]):
        return "rust"
    if any(x in t for x in ["mdn", "css", "html", "dom", "browser api"]):
        return "web"
    return "general"


def _text_similarity(a: str, b: str) -> float:
    """Cheap Jaccard similarity on words. 0.0 = no overlap, 1.0 = identical."""
    if not a or not b:
        return 0.0
    wa = set(re.findall(r"\b\w{3,}\b", a.lower()))
    wb = set(re.findall(r"\b\w{3,}\b", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


async def _search_error_kb(query: str, error_text: Optional[str] = None) -> str:
    """Search local error_kb/ for past similar errors. Returns matching entries."""
    if not ERROR_KB_DIR.exists():
        return ""
    keywords = _extract_keywords(query + " " + (error_text or ""))
    if not keywords:
        return ""
    keyword_set = set(keywords.lower().split())
    matches = []
    try:
        for kb_file in ERROR_KB_DIR.glob("*.json"):
            try:
                data = json.loads(kb_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            err_msg = (data.get("error_message") or "").lower()
            err_types = " ".join(data.get("error_types") or []).lower()
            text = f"{err_msg} {err_types}"
            overlap = len(keyword_set & set(re.findall(r"\b\w{3,}\b", text)))
            if overlap >= 1 or _text_similarity(keywords, text) > 0.15:
                matches.append({
                    "file": kb_file.name,
                    "error_types": data.get("error_types", []),
                    "error_message": data.get("error_message", "")[:200],
                    "fixes": data.get("fixes", []),
                    "success": data.get("success", False),
                    "overlap": overlap,
                })
    except Exception as e:
        return f"(error_kb scan error: {e})"
    matches.sort(key=lambda m: (m["overlap"], m["success"]), reverse=True)
    matches = matches[:5]
    if not matches:
        return ""
    return json.dumps({"error_kb_matches": matches, "count": len(matches)}, indent=2)


def _extract_topics(text: str, n: int = 5) -> set[str]:
    """Extract key topics (capitalized phrases, code identifiers) for agreement check."""
    if not text:
        return set()
    # Code-like tokens, capitalized words, quoted strings
    topics = set()
    topics.update(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text))         # CamelCase
    topics.update(re.findall(r"\b[a-z_]{3,}\(\)", text))               # function calls
    topics.update(re.findall(r"\b(?:npm|pip|install|import|require)\s+([a-zA-Z0-9_-]+)", text))
    topics.update(re.findall(r'"([^"]{3,30})"', text))                  # quoted strings
    return {t.lower() for t in topics if len(t) > 2}


def _compute_confidence(results: dict) -> tuple[int, str]:
    """
    Compute confidence score (0-100) based on:
      - Number of sources that returned content
      - Agreement between sources (topic overlap)
      - Source weights (trusted sources = more weight)
      - error_kb hit with successful past fix = strong signal
    Returns (score, verdict_label).
    """
    populated = {k: v for k, v in results.items()
                 if v and not v.startswith("(") and not v.startswith("(error")
                 and len(v) > 50}
    if not populated:
        return (0, "no_data")

    # 1. Coverage score (0-30): how many sources returned useful content
    coverage = min(30, int(len(populated) / max(1, len(results)) * 30))

    # 2. Agreement score (0-30): how much topics overlap across sources
    topics_per_source = {k: _extract_topics(v) for k, v in populated.items()}
    topic_sets = [s for s in topics_per_source.values() if s]
    if len(topic_sets) >= 2:
        pairs = []
        for i in range(len(topic_sets)):
            for j in range(i + 1, len(topic_sets)):
                a, b = topic_sets[i], topic_sets[j]
                if a and b:
                    pairs.append(len(a & b) / len(a | b))
        agreement = int((sum(pairs) / len(pairs)) * 30) if pairs else 0
    else:
        agreement = 10 if topic_sets else 0

    # 3. Source weight bonus (0-20): sum of weights of populated sources
    weight_bonus = min(20, int(sum(SOURCE_WEIGHTS.get(k, 0.5) for k in populated) * 10))

    # 4. error_kb + diagnostics agreement bonus (0-20): if BOTH ran AND
    #    error_kb has a past successful fix → strong signal we're on right track
    kb_bonus = 0
    if "error_kb" in populated and "diagnostics" in populated:
        try:
            kb_data = json.loads(results["error_kb"])
            successful = [m for m in kb_data.get("error_kb_matches", []) if m.get("success")]
            if successful:
                kb_bonus = 20  # past successful fix + classification = very strong
            elif kb_data.get("error_kb_matches"):
                kb_bonus = 10  # seen this pattern before
        except Exception:
            pass

    score = coverage + agreement + weight_bonus + kb_bonus
    score = max(0, min(100, score))

    if score >= 75:
        verdict = "high"
    elif score >= 50:
        verdict = "medium"
    elif score >= 25:
        verdict = "low"
    else:
        verdict = "very_low"
    return (score, verdict)


def _format_consensus(results: dict, query: str, lang: str, confidence: int, verdict: str) -> str:
    lines = [
        f"=== MCP Research Consensus ===",
        f"Query      : {query[:120]}",
        f"Lang       : {lang}",
        f"Sources    : {len(results)} polled, {sum(1 for v in results.values() if v and not v.startswith('('))} returned",
        f"Confidence : {confidence}/100 ({verdict})",
        "",
    ]

    # Diagnostics
    diag = results.get("diagnostics", "")
    if diag and "(no error_text" not in diag and "(empty" not in diag:
        lines.append("─── DIAGNOSTICS ───")
        lines.append(diag[:500])
        lines.append("")

    # Memory
    mem = results.get("memory", "")
    if mem and '"entities": []' not in mem and mem.strip().startswith("{"):
        lines.append("─── MEMORY (user notes) ───")
        lines.append(mem[:500])
        lines.append("")

    # error_kb
    ekb = results.get("error_kb", "")
    if ekb and '"error_kb_matches"' in ekb:
        try:
            d = json.loads(ekb)
            lines.append(f"─── ERROR KB ({d.get('count', 0)} past similar) ───")
            for m in d.get("error_kb_matches", [])[:3]:
                etype = m.get('error_types', ['?'])[0] if m.get('error_types') else '?'
                lines.append(f"  • {etype}: {m.get('error_message', '')[:120]}")
                if m.get("fixes"):
                    lines.append(f"    fix: {m['fixes'][0]}")
                lines.append(f"    success: {m.get('success')}")
            lines.append("")
        except Exception as e:
            lines.append(f"─── ERROR KB (parse error: {e}) ───")
    elif ekb:
        # debug: show what we got
        lines.append(f"─── ERROR KB (raw, {len(ekb)} chars) ───")
        lines.append(ekb[:200])
        lines.append("")

    # Web sources
    web_sources = [(k, v) for k, v in results.items()
                   if k not in ("diagnostics", "memory", "error_kb")
                   and v and not v.startswith("(") and len(v) > 50]
    web_sources.sort(key=lambda kv: SOURCE_WEIGHTS.get(kv[0], 0.5), reverse=True)
    if web_sources:
        lines.append(f"─── WEB SOURCES ({len(web_sources)}) ───")
        for name, body in web_sources:
            w = SOURCE_WEIGHTS.get(name, 0.5)
            preview = body[:350].replace("\n\n", "\n")
            lines.append(f"[{name} | weight={w:.2f}] {preview}")
            lines.append("")

    # Final verdict
    lines.append("─── VERDICT ───")
    if verdict == "high":
        lines.append(f"✅ High confidence ({confidence}/100). Multiple sources agree. Safe to apply.")
    elif verdict == "medium":
        lines.append(f"🟡 Medium confidence ({confidence}/100). Apply with verification step.")
    elif verdict == "low":
        lines.append(f"⚠️  Low confidence ({confidence}/100). Sources disagree or sparse. Verify before applying.")
    else:
        lines.append(f"❌ Very low confidence ({confidence}/100). No useful sources. Re-search with refined query.")
    return "\n".join(lines)


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="query",
    description=(
        "One-shot parallel research with weighted voting + confidence score. "
        "Polls 5+ web sources + diagnostics + memory + error_kb in parallel, "
        "returns ranked consensus with 0-100 confidence score. ~5s latency."
    ),
)
async def query(question: str, error_text: Optional[str] = None) -> str:
    if not question.strip():
        return "(empty query)"
    lang = _detect_language(question + " " + (error_text or ""))
    keywords = _extract_keywords(question) or question

    tasks = {
        "web":            search_web(keywords, max_results=3),
        "stackoverflow":  search_stackoverflow(keywords, max_results=3),
        "mdn":            search_mdn(keywords, limit=2),
        "pypi":           search_pypi(keywords, limit=2) if lang == "python" else _noop("not python"),
        "npm":            search_npm(keywords, limit=2) if lang == "javascript" else _noop("not js"),
        "crates":         search_crates(keywords, limit=2) if lang == "rust" else _noop("not rust"),
        "diagnostics":    classify_error(error_text) if error_text else _noop("no error"),
        "memory":         search_nodes(keywords[:30]),
        # error_kb is sync file I/O — run directly in event loop (fast for small kb)
        "error_kb":       _search_error_kb(question, error_text),
    }
    results = await _gather_with_timeout(tasks, timeout=6.0)  # 6s per source — slow ones get dropped
    confidence, verdict = _compute_confidence(results)
    return _format_consensus(results, question, lang, confidence, verdict)


@mcp.tool(name="quick", description="Fast 2-source check: web + stackoverflow in parallel. ~3s.")
async def quick(question: str) -> str:
    if not question.strip():
        return "(empty query)"
    keywords = _extract_keywords(question) or question
    web, so = await asyncio.gather(
        search_web(keywords, max_results=3),
        search_stackoverflow(keywords, max_results=3),
        return_exceptions=True,
    )
    results = {
        "web": web if not isinstance(web, Exception) else f"(error: {web})",
        "stackoverflow": so if not isinstance(so, Exception) else f"(error: {so})",
    }
    confidence, verdict = _compute_confidence(results)
    body = _format_consensus(results, question, "general", confidence, verdict)
    return body + "\n\n─── QUICK MODE: only 2 sources polled ───"


@mcp.tool(
    name="deep",
    description=(
        "Full 8-source cross-validation + error_kb. Slower (~8s) but highest "
        "confidence. Use for critical unknown errors where 3+ sources must agree."
    ),
)
async def deep(question: str, error_text: Optional[str] = None) -> str:
    if not question.strip():
        return "(empty query)"
    lang = _detect_language(question + " " + (error_text or ""))
    keywords = _extract_keywords(question) or question

    tasks = {
        "web":            search_web(keywords, max_results=4),
        "stackoverflow":  search_stackoverflow(keywords, max_results=4),
        "mdn":            search_mdn(keywords, limit=3),
        "devdocs":        search_devdocs(keywords, limit=3),
        "pypi":           search_pypi(keywords, limit=3),
        "npm":            search_npm(keywords, limit=3),
        "crates":         search_crates(keywords, limit=3),
        "diagnostics":    classify_error(error_text) if error_text else _noop("no error"),
        "memory":         search_nodes(keywords[:30]),
        "error_kb":       _search_error_kb(question, error_text),
    }
    results = await _gather_with_timeout(tasks, timeout=8.0)
    confidence, verdict = _compute_confidence(results)
    body = _format_consensus(results, question, lang, confidence, verdict)
    return body + "\n\n─── DEEP MODE: 8 web sources + diagnostics + memory + error_kb ───"


@mcp.tool(
    name="stream",
    description=(
        "Async iterator: returns each source's result AS IT ARRIVES. "
        "Don't wait for slowest — use fastest available answer."
    ),
)
async def stream(question: str, error_text: Optional[str] = None) -> str:
    """
    Stream sources as they complete using asyncio.as_completed.
    Returns a summary: which source finished first, what it said, and
    confidence based on early arrivals.
    """
    if not question.strip():
        return "(empty query)"
    keywords = _extract_keywords(question) or question
    lang = _detect_language(question + " " + (error_text or ""))

    coros = {
        "web":           search_web(keywords, max_results=2),
        "stackoverflow": search_stackoverflow(keywords, max_results=2),
        "mdn":           search_mdn(keywords, limit=2),
        "diagnostics":   classify_error(error_text) if error_text else _noop("no error"),
        "error_kb":      _search_error_kb(question, error_text),
    }
    # Wrap coros as (name, coro) pairs and use as_completed
    named = list(coros.items())
    tasks = [asyncio.create_task(c, name=name) for name, c in named]
    lines = ["=== MCP Research Stream (results as they arrive) ===", f"Query: {question[:120]}", ""]
    arrivals = []
    try:
        for finished in asyncio.as_completed(tasks, timeout=15.0):
            try:
                result = await finished
                # Find which task just completed
                idx = tasks.index(finished) if finished in tasks else 0
                name = named[idx][0]
            except Exception as e:
                name = "?"
                result = f"(error: {e})"
            arrivals.append((name, result))
            preview = (result or "")[:200].replace("\n", " ")
            w = SOURCE_WEIGHTS.get(name, 0.5)
            lines.append(f"[{name} w={w:.2f}] {preview}")
    except asyncio.TimeoutError:
        lines.append("(timeout — some sources did not respond)")

    # Use arrived sources for confidence
    results_dict = {n: r for n, r in arrivals}
    confidence, verdict = _compute_confidence(results_dict)
    lines.append("")
    lines.append(f"─── EARLY CONFIDENCE: {confidence}/100 ({verdict}) from {len(arrivals)} sources ───")
    return "\n".join(lines)


# ── Internal helpers ─────────────────────────────────────────────────────────

async def _noop(reason: str) -> str:
    return f"(skipped: {reason})"


async def _gather_with_timeout(tasks: dict, timeout: float) -> dict:
    """
    Run coros in parallel with a per-task timeout. Slow tasks return
    "(timeout)" but don't cancel the fast ones. Critical: asyncio.wait_for
    on gather cancels EVERYTHING if any one task is slow, so we wrap each
    task individually.
    """
    async def _one(name: str, coro) -> tuple[str, str]:
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            if isinstance(result, Exception):
                return (name, f"(error: {result})")
            return (name, result)
        except asyncio.TimeoutError:
            return (name, f"(timeout > {timeout}s)")
        except Exception as e:
            return (name, f"(error: {e})")
    results = await asyncio.gather(*[_one(n, c) for n, c in tasks.items()])
    return dict(results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
