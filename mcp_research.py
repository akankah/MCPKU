"""
mcp_research.py — MCPKU Parallel Research Aggregator (v3)
==========================================================
Semantic consensus engine. Uses embedding-based similarity for
source agreement detection and structured JSON output.

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

import numpy as np
from mcp.server.fastmcp import FastMCP

from mcp_web import (
    search_web,
    search_stackoverflow,
    search_npm,
    search_pypi,
    search_mdn,
    search_crates,
    search_devdocs,
    search_readthedocs,
)
from mcp_diagnostics import classify_error
from mcp_memory import search_nodes
from mcp_vector import _embed

mcp = FastMCP(
    "mcp-research",
    instructions=(
        "Parallel research orchestrator with semantic consensus + confidence scoring. "
        "Use query() when you need a single consensus answer cross-checked across "
        "multiple sources. Runs 6 web sources + diagnostics + memory + error_kb "
        "in parallel via asyncio.gather, returns structured JSON with explicit "
        "confidence score (0-100%).\n\n"
        "AUTOFALLBACK (mandatory): if any other reasoning path takes > 10s without "
        "progress, or you are about to retry a failing approach, call query() (or "
        "quick()/deep()) IMMEDIATELY instead of guessing. Skip only for trivial "
        "lookups. See AGENTS.md for full rule.\n\n"
        "When to use:\n"
        "  - Complex unknown error (autofix/diagnostics flagged UNKNOWN)\n"
        "  - API/library/framework behavior you're not 100% sure about\n"
        "  - User asks a research question that benefits from multi-source confirmation\n\n"
        "When NOT to use:\n"
        "  - Trivial lookups (use mcp_web.search_web directly)\n"
        "  - Single-source docs check (use mcp_web.search_mdn / search_npm directly)\n"
        "  - Renames / typos / file reads\n\n"
        "Return value is always structured JSON: "
        "{success, tool, confidence: {score, verdict, ...}, sources: [...], "
        "consensus_topics: [...], recommended_fix, ...}"
    ),
)

SOURCE_WEIGHTS = {
    "stackoverflow": 0.90,
    "github":        0.85,
    "mdn":           0.95,
    "pypi":          0.80,
    "npm":           0.80,
    "crates":        0.80,
    "devdocs":       0.85,
    "error_kb":      0.95,
    "memory":        0.75,
    "diagnostics":   0.85,
    "web":           0.50,
}

ERROR_KB_DIR = Path(os.environ.get("ERROR_KB_DIR", Path(__file__).parent / "error_kb"))


# ── Semantic similarity via embeddings (async-safe) ──────────────────────────

_EMBED_TIMEOUT = 2.0  # seconds max for embedding call


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a = np.array(a, dtype=np.float64)
    b = np.array(b, dtype=np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


async def _embed_async(texts: list[str]) -> list[list[float] | None]:
    """Async wrapper for _embed with timeout. Returns None-filled list on failure."""
    try:
        embs = await asyncio.wait_for(
            asyncio.to_thread(_embed, texts),
            timeout=_EMBED_TIMEOUT,
        )
        return embs if embs else [None] * len(texts)
    except Exception:
        return [None] * len(texts)


async def _semantic_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    embs = await _embed_async([a[:500], b[:500]])
    if len(embs) >= 2 and embs[0] is not None and embs[1] is not None:
        return _cosine_similarity(embs[0], embs[1])
    # Fallback: lexical Jaccard on words
    return _lexical_similarity(a, b)


def _lexical_similarity(a: str, b: str) -> float:
    wa = set(re.findall(r"\b\w{3,}\b", a.lower()))
    wb = set(re.findall(r"\b\w{3,}\b", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ── Semantic source clustering (async) ───────────────────────────────────────

async def _cluster_sources(source_texts: dict[str, str]) -> list[list[str]]:
    """
    Group sources into semantic clusters using embedding cosine similarity.
    Returns list of clusters, where each cluster is a list of source names.
    """
    names = list(source_texts.keys())
    texts = [source_texts[n][:500] for n in names]
    if len(texts) < 2:
        return [names]

    embs = await _embed_async(texts)
    if not embs or all(e is None for e in embs):
        return [names]

    sim_matrix = []
    for i in range(len(embs)):
        row = []
        for j in range(len(embs)):
            if embs[i] is not None and embs[j] is not None:
                row.append(_cosine_similarity(embs[i], embs[j]))
            else:
                row.append(_lexical_similarity(texts[i], texts[j]))
        sim_matrix.append(row)

    THRESHOLD = 0.50
    assigned = set()
    clusters = []
    for i in range(len(names)):
        if i in assigned:
            continue
        cluster = [names[i]]
        assigned.add(i)
        for j in range(i + 1, len(names)):
            if j not in assigned and sim_matrix[i][j] >= THRESHOLD:
                cluster.append(names[j])
                assigned.add(j)
        clusters.append(cluster)
    return clusters


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
    filtered = [w for w in words if w not in stop]
    return " ".join(filtered[:max_words])


def _detect_language(text: str) -> str:
    if not text:
        return "general"
    t = text.lower()
    if any(x in t for x in ["npm", "node", "javascript", "typescript", "react", "vue", "next.js"]):
        return "javascript"
    if any(x in t for x in ["pip", "python", "django", "flask", "fastapi"]) or \
       any(x in t for x in ["modulenotfounderror", "importerror", "indentationerror",
                             "syntaxerror", "attributeerror", "pyfile"]):
        return "python"
    if any(x in t for x in ["cargo", "rust", "crate", "rustc"]):
        return "rust"
    if any(x in t for x in ["mdn", "css", "html", "dom", "browser api"]):
        return "web"
    return "general"


async def _search_error_kb(query: str, error_text: Optional[str] = None) -> str:
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
            if overlap >= 1 or _lexical_similarity(keywords, text) > 0.15:
                matches.append({
                    "file": kb_file.name,
                    "error_types": data.get("error_types", []),
                    "error_message": data.get("error_message", "")[:200],
                    "fixes": data.get("fixes", []),
                    "success": data.get("success", False),
                    "overlap": overlap,
                })
    except Exception as e:
        return json.dumps({"error_kb_error": str(e)})
    matches.sort(key=lambda m: (m["overlap"], m["success"]), reverse=True)
    matches = matches[:5]
    if not matches:
        return ""
    return json.dumps({"error_kb_matches": matches, "count": len(matches)}, indent=2)


def _try_parse_json(s: str) -> Optional[dict]:
    if not s:
        return None
    if s.strip().startswith("{"):
        try:
            return json.loads(s)
        except Exception:
            pass
    return None


# ── Confidence (semantic-aware) ──────────────────────────────────────────────

async def _compute_confidence(results: dict, query: str) -> dict:
    """
    Compute confidence score (0-100) using semantic source clustering.
    Returns structured confidence dict.
    """
    populated = {k: v for k, v in results.items()
                 if v and not v.startswith("(") and not v.startswith("(error")
                 and len(v) > 50}
    if not populated:
        return {"score": 0, "verdict": "no_data", "coverage": 0, "agreement": 0,
                "weight_bonus": 0, "kb_bonus": 0, "clusters": []}

    # 1. Coverage score (0-30)
    coverage = min(30, int(len(populated) / max(1, len(results)) * 30))

    # 2. Semantic agreement score (0-30) via embedding clusters
    clusters = await _cluster_sources(populated)
    # More clusters = less agreement. Best: 1 cluster = all agree.
    if len(clusters) <= 1:
        agreement = 30
    elif len(clusters) == 2:
        agreement = 20
    elif len(clusters) == 3:
        agreement = 10
    else:
        agreement = 5

    # Bonus if the largest cluster covers > 60% of populated sources
    largest_cluster_size = max(len(c) for c in clusters) if clusters else 0
    cluster_ratio = largest_cluster_size / max(1, len(populated))
    if cluster_ratio >= 0.6:
        agreement = min(30, agreement + 10)

    # 3. Source weight bonus (0-20)
    weight_bonus = min(20, int(sum(SOURCE_WEIGHTS.get(k, 0.5) for k in populated) * 10))

    # 4. error_kb + diagnostics bonus (0-20)
    kb_bonus = 0
    if "error_kb" in populated and "diagnostics" in populated:
        kb_data = _try_parse_json(results["error_kb"])
        if kb_data:
            successful = [m for m in kb_data.get("error_kb_matches", []) if m.get("success")]
            if successful:
                kb_bonus = 20
            elif kb_data.get("error_kb_matches"):
                kb_bonus = 10

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

    return {
        "score": score,
        "verdict": verdict,
        "coverage": coverage,
        "agreement": agreement,
        "weight_bonus": weight_bonus,
        "kb_bonus": kb_bonus,
        "clusters": clusters,
        "cluster_ratio": round(cluster_ratio, 2),
        "sources_returned": len(populated),
        "sources_total": len(results),
    }


# ── Structured output builder ────────────────────────────────────────────────

def _build_result(tool_name: str, question: str, results: dict,
                  confidence: dict, lang: str) -> str:
    """Build structured JSON result from all sources."""
    populated = {k: v for k, v in results.items()
                 if v and not v.startswith("(") and not v.startswith("(error")
                 and len(v) > 50}
    empty_sources = {k: v for k, v in results.items() if k not in populated}

    # Build sources list
    sources = []
    for name in sorted(populated, key=lambda n: SOURCE_WEIGHTS.get(n, 0.5), reverse=True):
        body = populated[name]
        source_entry = {
            "name": name,
            "weight": SOURCE_WEIGHTS.get(name, 0.5),
            "preview": body[:500],
        }
        # Parse error_kb JSON inline
        if name == "error_kb":
            parsed = _try_parse_json(body)
            if parsed:
                source_entry["matches"] = parsed.get("error_kb_matches", [])
                source_entry["match_count"] = parsed.get("count", 0)
        sources.append(source_entry)

    for name in sorted(empty_sources):
        body = empty_sources[name]
        reason = "empty"
        if body.startswith("(") or body.startswith("(error") or body.startswith("(timeout"):
            reason = body.strip("()")
        elif body.startswith("(skip"):
            reason = "skipped"
        sources.append({
            "name": name,
            "weight": SOURCE_WEIGHTS.get(name, 0.5),
            "preview": body[:200],
            "status": reason,
        })

    # Build consensus topics from largest cluster
    clusters = confidence.get("clusters", [])
    consensus_topics = []
    if clusters:
        largest = max(clusters, key=len)
        consensus_topics = [s for s in largest if s != "diagnostics" and s != "error_kb"]

    # Recommended fix from error_kb if available
    recommended_fix = None
    for s in sources:
        if s.get("name") == "error_kb" and s.get("matches"):
            successful = [m for m in s["matches"] if m.get("success")]
            if successful:
                fixes = successful[0].get("fixes", [])
                if fixes:
                    recommended_fix = fixes[0]

    output = {
        "success": True,
        "tool": tool_name,
        "query": question[:500],
        "language": lang,
        "confidence": confidence,
        "sources": sources,
        "consensus_topics": consensus_topics,
        "recommended_fix": recommended_fix,
        "sources_returned": len(populated),
        "sources_total": len(results),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="query",
    description=(
        "One-shot parallel research with semantic consensus + confidence score. "
        "Polls 5+ web sources + diagnostics + memory + error_kb in parallel, "
        "returns structured JSON with 0-100 confidence score. ~5s latency."
    ),
)
async def query(question: str, error_text: Optional[str] = None) -> str:
    if not question.strip():
        return json.dumps({"success": False, "tool": "query", "error": "empty query"})
    lang = _detect_language(question + " " + (error_text or ""))
    keywords = _extract_keywords(question) or question

    tasks = {
        "web":            search_web(keywords, max_results=3),
        "stackoverflow":  search_stackoverflow(keywords, max_results=3),
        "mdn":            search_mdn(keywords, limit=2),
        "readthedocs":    search_readthedocs(keywords, limit=2) if lang == "python" else _noop("not python"),
        "pypi":           search_pypi(keywords, limit=2) if lang == "python" else _noop("not python"),
        "npm":            search_npm(keywords, limit=2) if lang == "javascript" else _noop("not js"),
        "crates":         search_crates(keywords, limit=2) if lang == "rust" else _noop("not rust"),
        "diagnostics":    classify_error(error_text) if error_text else _noop("no error"),
        "memory":         search_nodes(keywords[:30]),
        "error_kb":       _search_error_kb(question, error_text),
    }
    results = await _gather_with_timeout(tasks, timeout=6.0)
    confidence = await _compute_confidence(results, question)
    return _build_result("query", question, results, confidence, lang)


@mcp.tool(name="quick", description="Fast 2-source check: web + stackoverflow in parallel. ~3s.")
async def quick(question: str) -> str:
    if not question.strip():
        return json.dumps({"success": False, "tool": "quick", "error": "empty query"})
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
    confidence = await _compute_confidence(results, question)
    result = _build_result("quick", question, results, confidence, "general")
    # Add quick-mode note
    d = json.loads(result)
    d["mode"] = "quick (2 sources only)"
    return json.dumps(d, indent=2, ensure_ascii=False)


@mcp.tool(
    name="deep",
    description=(
        "Full 8-source cross-validation + error_kb. Slower (~8s) but highest "
        "confidence. Returns structured JSON. Use for critical unknown errors "
        "where 3+ sources must agree."
    ),
)
async def deep(question: str, error_text: Optional[str] = None) -> str:
    if not question.strip():
        return json.dumps({"success": False, "tool": "deep", "error": "empty query"})
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
    confidence = await _compute_confidence(results, question)
    result = _build_result("deep", question, results, confidence, lang)
    d = json.loads(result)
    d["mode"] = "deep (8 sources + diagnostics + memory + error_kb)"
    return json.dumps(d, indent=2, ensure_ascii=False)


@mcp.tool(
    name="stream",
    description=(
        "Async iterator: returns each source's result AS IT ARRIVES. "
        "Don't wait for slowest — use fastest available answer. "
        "Returns structured JSON."
    ),
)
async def stream(question: str, error_text: Optional[str] = None) -> str:
    if not question.strip():
        return json.dumps({"success": False, "tool": "stream", "error": "empty query"})
    keywords = _extract_keywords(question) or question
    lang = _detect_language(question + " " + (error_text or ""))

    coros = {
        "web":           search_web(keywords, max_results=2),
        "stackoverflow": search_stackoverflow(keywords, max_results=2),
        "mdn":           search_mdn(keywords, limit=2),
        "diagnostics":   classify_error(error_text) if error_text else _noop("no error"),
        "error_kb":      _search_error_kb(question, error_text),
    }
    named = list(coros.items())
    tasks = [asyncio.create_task(c, name=name) for name, c in named]
    arrivals = []
    try:
        for finished in asyncio.as_completed(tasks, timeout=15.0):
            try:
                result = await finished
                idx = tasks.index(finished)
                name = named[idx][0]
            except Exception as e:
                name = "?"
                result = f"(error: {e})"
            arrivals.append({"name": name, "result": result[:500]})
    except asyncio.TimeoutError:
        pass

    results_dict = {a["name"]: a["result"] for a in arrivals}
    confidence = await _compute_confidence(results_dict, question)
    output = {
        "success": True,
        "tool": "stream",
        "query": question[:500],
        "language": lang,
        "confidence": confidence,
        "arrivals": arrivals,
        "arrival_count": len(arrivals),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ── Internal helpers ─────────────────────────────────────────────────────────

async def _noop(reason: str) -> str:
    return f"(skipped: {reason})"


async def _gather_with_timeout(tasks: dict, timeout: float) -> dict:
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
