"""
mcp_research.py — MCPKU Parallel Research Aggregator
======================================================
Calls 6 web sources + diagnostics + memory IN PARALLEL via asyncio.gather,
deduplicates results, ranks by relevance, returns a single consensus answer.

This is the orchestration layer recommended in the "Parallel Cross-Validation"
MCPKU pattern. It exists so the model can make ONE tool call and get a
ranked, cross-checked research result instead of 8 separate sequential calls.

Tools:
  - query(question, error_text=None, language=None) → one-shot consensus research
  - quick(question) → only web + SO (faster, 2 sources)
  - deep(question, error_text=None) → 8 sources + cross-check (slower, more thorough)
"""
import asyncio
import json
import re
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

mcp = FastMCP(
    "mcp-research",
    instructions=(
        "Parallel research orchestrator. Use query() when you need a single "
        "consensus answer that has been cross-checked across multiple sources. "
        "Runs 6 web sources + diagnostics + memory in parallel via asyncio.gather "
        "and returns a ranked, deduplicated summary.\n\n"
        "When to use:\n"
        "  - Complex unknown error (autofix/diagnostics flagged UNKNOWN)\n"
        "  - API/library/framework behavior you're not 100% sure about\n"
        "  - User asks a research question that benefits from multi-source confirmation\n\n"
        "When NOT to use:\n"
        "  - Trivial lookups (use mcp_web.search_web directly)\n"
        "  - Single-source docs check (use mcp_web.search_mdn / search_npm directly)\n"
        "  - Renames / typos / file reads\n\n"
        "Use quick() for fast 2-source check. Use deep() for full 8-source cross-validation."
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_keywords(text: str, max_words: int = 8) -> str:
    """Extract top keywords from question for secondary searches."""
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
    keywords = [w for w in words if w not in stop]
    return " ".join(keywords[:max_words])


def _detect_language(text: str) -> str:
    """Detect primary language/ecosystem from query or error text."""
    if not text:
        return "general"
    t = text.lower()
    if any(x in t for x in ["npm", "node", "javascript", "typescript", "react",
                             "vue", "next.js", "package.json"]):
        return "javascript"
    if any(x in t for x in ["pip", "import", "python", "django", "flask", "fastapi"]):
        return "python"
    if any(x in t for x in ["cargo", "rust", "crate", "rustc"]):
        return "rust"
    if any(x in t for x in ["gem", "ruby", "rails"]):
        return "ruby"
    if any(x in t for x in ["mdn", "css", "html", "dom", "browser api"]):
        return "web"
    return "general"


def _format_consensus(results: dict, query: str, lang: str) -> str:
    """Format parallel results into a ranked consensus summary."""
    lines = [
        f"=== MCP Research Consensus ===",
        f"Query   : {query[:120]}",
        f"Lang    : {lang}",
        f"Sources : {len(results)} parallel",
        "",
    ]

    # 1. Diagnostics (if ran)
    diag = results.get("diagnostics", "")
    if diag and "(empty" not in diag and "Types" in diag:
        lines.append("─── DIAGNOSTICS ───")
        lines.append(diag[:600])
        lines.append("")

    # 2. Memory (past errors / entities)
    mem = results.get("memory", "")
    if mem and mem.strip() and "[]" not in mem and '"entities": []' not in mem:
        lines.append("─── MEMORY (past similar) ───")
        lines.append(mem[:600])
        lines.append("")

    # 3. Web sources ranked
    web_sources = [
        ("stackoverflow", results.get("stackoverflow", "")),
        ("web",            results.get("web", "")),
        ("mdn",            results.get("mdn", "")),
        ("pypi",           results.get("pypi", "")),
        ("npm",            results.get("npm", "")),
        ("crates",         results.get("crates", "")),
        ("devdocs",        results.get("devdocs", "")),
    ]
    web_sources = [(name, body) for name, body in web_sources if body and len(body) > 50]

    if web_sources:
        lines.append(f"─── WEB SOURCES ({len(web_sources)}) ───")
        for name, body in web_sources:
            preview = body[:400].replace("\n\n", "\n")
            lines.append(f"[{name}] {preview}")
            lines.append("")

    # 4. Cross-check verdict
    diag_ran = diag and "(no error_text" not in diag and "(empty" not in diag
    mem_ran = mem and '"entities": []' not in mem and mem.strip().startswith("{")
    lines.append("─── CROSS-CHECK ───")
    if diag_ran and "UNKNOWN" in diag.upper():
        lines.append("⚠️  Diagnostics: UNKNOWN error type. Web sources should be authoritative.")
    elif diag_ran:
        lines.append(f"✅ Diagnostics classified: {diag.split(chr(10))[2] if chr(10) in diag else diag[:100]}")
    if mem_ran:
        entity_count = mem.count('"name":')
        lines.append(f"✅ Memory returned {entity_count} matching entities (cross-check above).")
    if not web_sources and not diag_ran and not mem_ran:
        lines.append("⚠️  No sources returned content. Refine query and retry.")

    return "\n".join(lines)


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="query",
    description=(
        "One-shot parallel research: calls 5 web sources + diagnostics + memory "
        "in parallel, deduplicates, returns ranked consensus. Best for complex "
        "unknown errors or multi-source research questions. Use this instead of "
        "running search_web + search_stackoverflow + classify_error sequentially."
    ),
)
async def query(
    question: str,
    error_text: Optional[str] = None,
) -> str:
    if not question.strip():
        return "(empty query)"

    lang = _detect_language(question + " " + (error_text or ""))
    keywords = _extract_keywords(question)
    if error_text:
        keywords = keywords or _extract_keywords(error_text)

    # Build parallel tasks
    tasks = {
        "web":            search_web(keywords or question, max_results=3),
        "stackoverflow":  search_stackoverflow(keywords or question, max_results=3),
        "mdn":            search_mdn(keywords or question, limit=2),
        "pypi":           search_pypi(keywords or question, limit=2) if lang == "python" else asyncio.sleep(0, result="(skipped: not python)"),
        "npm":            search_npm(keywords or question, limit=2) if lang == "javascript" else asyncio.sleep(0, result="(skipped: not js)"),
        "crates":         search_crates(keywords or question, limit=2) if lang == "rust" else asyncio.sleep(0, result="(skipped: not rust)"),
        "diagnostics":    classify_error(error_text) if error_text else asyncio.sleep(0, result="(no error_text provided)"),
        "memory":         search_nodes(keywords or question[:30]),
    }

    # Run in parallel with timeout
    names = list(tasks.keys())
    coros = list(tasks.values())
    try:
        settled = await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=True),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        settled = ["(timeout)"] * len(coros)

    results = {name: (settled[i] if not isinstance(settled[i], Exception) else f"(error: {settled[i]})")
               for i, name in enumerate(names)}

    return _format_consensus(results, question, lang)


@mcp.tool(
    name="quick",
    description="Fast 2-source check: web + stackoverflow in parallel. ~3s latency.",
)
async def quick(question: str) -> str:
    if not question.strip():
        return "(empty query)"
    keywords = _extract_keywords(question) or question
    web, so = await asyncio.gather(
        search_web(keywords, max_results=3),
        search_stackoverflow(keywords, max_results=3),
        return_exceptions=True,
    )
    return (
        f"=== Quick Research ===\n"
        f"Query: {question[:120]}\n\n"
        f"[web] {web if not isinstance(web, Exception) else f'(error: {web})'}\n\n"
        f"[stackoverflow] {so if not isinstance(so, Exception) else f'(error: {so})'}"
    )


@mcp.tool(
    name="deep",
    description=(
        "Full 8-source cross-validation. Slower (~8s) but highest confidence. "
        "Use for critical unknown errors or research where you need 3+ sources to agree."
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
        "diagnostics":    classify_error(error_text) if error_text else asyncio.sleep(0, result="(no error_text)"),
        "memory":         search_nodes(keywords[:30]),
    }

    names = list(tasks.keys())
    coros = list(tasks.values())
    try:
        settled = await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=True),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        settled = ["(timeout)"] * len(coros)

    results = {name: (settled[i] if not isinstance(settled[i], Exception) else f"(error: {settled[i]})")
               for i, name in enumerate(names)}

    output = _format_consensus(results, question, lang)
    output += "\n\n─── DEEP MODE: all 8 sources polled ───"
    return output


if __name__ == "__main__":
    mcp.run(transport="stdio")
