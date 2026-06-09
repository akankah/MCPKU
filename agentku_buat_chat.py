"""
agentku_buat_chat.py — MCPKU Task Orchestrator (by akankah)
======================================
NO internal LLM calls. Relies on opencode's active model as the brain.
Provides planning + state management + orchestration helpers.

Why no LLM: opencode already has a model selected (/model).
MCPKU tools are called directly by that model. This module just
helps structure multi-step execution.

Architecture:
  agent_plan(goal) → structured JSON plan (which tools, what order)
  agent_status(id) → check execution state
  (external model calls MCPKU tools directly via the plan)
"""

import asyncio
import inspect
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP

from planner.intent_parser import parse_goal
from planner.task_graph import TaskGraph
from planner.dependency_solver import resolve_dependencies, order_by_dependencies
from planner.execution_policy import ExecutionPolicy

# ── Tool Registry + Metadata ──
_TOOL_REGISTRY: dict[str, Any] = {}
_TOOL_META: dict[str, dict] = {}
_policy = ExecutionPolicy()


def _reg(name: str, fn: Any, meta: dict = None):
    _TOOL_REGISTRY[name] = fn
    if meta:
        _TOOL_META[name] = meta


def _register_all():
    from mcp_manifest import register_all as _ra, get_tool
    _ra(_TOOL_REGISTRY)
    for name in list(_TOOL_REGISTRY.keys()):
        entry = get_tool(name)
        if entry:
            _TOOL_META.setdefault(name, {
                "category": entry.category,
                "dangerous": entry.dangerous,
                "requires_repo": entry.requires_repo,
                "requires_network": entry.requires_network,
                "timeout_suggestion": entry.timeout_suggestion,
                "parallel_ok": entry.parallel_ok,
            })


# ── Directories ──
_TEMP = Path(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp"))) / "mcpku"
PLANS_DIR = _TEMP / "plans"
PLANS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = _TEMP / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP(
    "mcp-agent",
    instructions=(
        "Task orchestrator for multi-step MCPKU execution. "
        "Use agent_plan() to generate a plan, then agent_execute() "
        "to run steps automatically. No internal LLM."
    ),
)


# ── Plan Generator ────────────────────────────────────────────────────────────

INTENT_TOOL_MAP: dict[str, list[dict]] = {
    "research": [
        {"tool": "auto_research", "desc": "Smart search + auto-fetch top URLs",
         "args": {"query": "{goal}", "max_fetch": 3}},
    ],
    "memory": [
        {"tool": "memory_search_nodes", "desc": "Search memory for existing related knowledge",
         "args": {"query": "{goal}"}},
        {"tool": "memory_create_entities", "desc": "Save key findings to memory",
         "args": {"entities": [{"name": "{name}", "entityType": "knowledge", "observations": ["From agent plan"]}]}},
    ],
    "debug": [
        {"tool": "diagnostics_parse_traceback", "desc": "Analyze the error",
         "args": {"traceback_text": "{context}"}},
        {"tool": "autofix_search_kb", "desc": "Check knowledge base for similar errors",
         "args": {"query": "{goal}"}},
        {"tool": "autofix_run", "desc": "Run and auto-fix",
         "args": {"command": "{context}", "max_retries": 3}},
    ],
    "files": [
        {"tool": "fs_grep_files", "desc": "Search relevant files",
         "args": {"pattern": "{context}", "path": "."}},
        {"tool": "fs_write_file", "desc": "Write output to file",
         "args": {"path": "output.md", "content": "# Result\n\n(TBD)"}},
    ],
    "git": [
        {"tool": "git_status", "desc": "Check repository status",
         "args": {"repo_path": ""}},
        {"tool": "git_log", "desc": "Show recent commits",
         "args": {"repo_path": "", "max_count": 10}},
    ],
    "time": [
        {"tool": "time_get_current_time", "desc": "Get current time",
         "args": {"timezone": "Asia/Jakarta"}},
    ],
    "plan": [
        {"tool": "planner_plan_generate", "desc": "Generate reusable workflow",
         "args": {"goal": "{goal}", "name": "{name}", "target_dir": ""}},
    ],
    "github": [
        {"tool": "github_search_issues", "desc": "Search GitHub issues",
         "args": {"query": "{goal}"}},
        {"tool": "github_list_issues", "desc": "List repo issues",
         "args": {"repo": "{context}"}},
    ],
    "db": [
        {"tool": "sqlite_list_tables", "desc": "List database tables",
         "args": {}},
    ],
    "think": [
        {"tool": "think", "desc": "Record reasoning step",
         "args": {"thought": "{goal}"}},
    ],
    "bash": [
        {"tool": "bash_run_command", "desc": "Run shell command",
         "args": {"command": "{goal}"}},
    ],
}


def _resolve_arg(template: Any, goal: str, context: str, name: str) -> Any:
    if isinstance(template, str):
        return template.replace("{goal}", goal[:120]).replace("{context}", context[:120]).replace("{name}", name[:50])
    if isinstance(template, dict):
        return {k: _resolve_arg(v, goal, context, name) for k, v in template.items()}
    if isinstance(template, list):
        return [_resolve_arg(v, goal, context, name) for v in template]
    return template


def _generate_plan(goal: str, context: str) -> dict:
    """Generate a structured execution plan with dependency ordering."""
    intents = parse_goal(goal, context)
    deps = resolve_dependencies(intents)
    ordered = order_by_dependencies(intents, deps)

    seen = set()
    steps = []
    graph = TaskGraph()
    goal_name = goal[:50]

    for intent in ordered:
        tool_specs = INTENT_TOOL_MAP.get(intent.action, [])
        for spec in tool_specs:
            key = f"{intent.action}_{spec['tool']}"
            if key not in seen:
                seen.add(key)
                step_id = f"step_{len(steps) + 1}"
                resolved_args = _resolve_arg(spec["args"], goal, context, goal_name)
                step = {
                    "id": step_id,
                    "category": intent.action,
                    "tool": spec["tool"],
                    "description": spec["desc"],
                    "args": resolved_args,
                    "status": "pending",
                    "depends_on": [],
                    "attempts": 0,
                    "failure_reason": "",
                    "tool_latency": 0.0,
                    "confidence": intent.confidence,
                    "policy": {
                        "max_retries": _policy.max_retries(intent.action),
                        "timeout": _policy.timeout(intent.action),
                        "critical": _policy.is_critical(intent.action),
                        "parallel_ok": _policy.can_parallel(intent.action),
                    },
                }
                steps.append(step)
                graph.add_node(step_id, {"intent": intent.action})

    return {
        "goal": goal,
        "context": context,
        "created": datetime.now().isoformat(),
        "steps": steps,
        "total_steps": len(steps),
        "metadata": {
            "version": "2.0",
            "planner": "planner/intent_parser + dependency_solver",
            "tool_source": "mcp_manifest.py",
        },
    }


# ── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool(
    name="agent_plan",
    description="Decompose a goal into an ordered execution plan with recommended MCPKU tools."
)
async def agent_plan(goal: str, context: str = "") -> str:
    """
    Generate a structured multi-step plan for achieving a goal.

    Args:
        goal: The objective (e.g., "research crypto trends, save to memory, generate report").
        context: Optional constraints, preferences, project path.
    """
    plan = _generate_plan(goal, context)
    plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    plan_path = PLANS_DIR / f"{plan_id}.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return json.dumps({"plan_id": plan_id, "plan": plan}, indent=2, ensure_ascii=False)


@mcp.tool(
    name="agent_status",
    description="Check the execution status of a previously generated plan."
)
async def agent_status(plan_id: str) -> str:
    """
    Check plan execution status from saved state.

    Args:
        plan_id: The plan ID returned by agent_plan().
    """
    plan_path = PLANS_DIR / f"{plan_id}.json"
    if not plan_path.exists():
        return f"Error: Plan '{plan_id}' not found."
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    completed = sum(1 for s in plan.get("steps", []) if s.get("status") == "completed")
    failed = sum(1 for s in plan.get("steps", []) if s.get("status") == "failed")
    total = len(plan.get("steps", []))
    return json.dumps({
        "plan_id": plan_id,
        "goal": plan.get("goal", ""),
        "progress": f"{completed}/{total}",
        "failed": failed,
        "steps": plan.get("steps", []),
    }, indent=2, ensure_ascii=False)


@mcp.tool(
    name="agent_mark_step",
    description="Mark a step as completed or failed in a plan. Updates the saved plan file."
)
async def agent_mark_step(plan_id: str, step_id: str, status: str, notes: str = "") -> str:
    """
    Update step status in a plan.

    Args:
        plan_id: Plan ID from agent_plan().
        step_id: Step ID (e.g., "step_1").
        status: "completed" or "failed".
        notes: Optional result summary.
    """
    plan_path = PLANS_DIR / f"{plan_id}.json"
    if not plan_path.exists():
        return f"Error: Plan '{plan_id}' not found."
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for step in plan.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = status
            step["completed_at"] = datetime.now().isoformat()
            if notes:
                step["notes"] = notes
            plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
            return f"Step {step_id} marked as {status}."
    return f"Error: Step '{step_id}' not found."


@mcp.tool(
    name="agent_list_plans",
    description="List all saved plans with their status."
)
async def agent_list_plans() -> str:
    """List all generated plans and their progress."""
    if not PLANS_DIR.exists():
        return "No plans found."
    plans = []
    for f in sorted(PLANS_DIR.glob("*.json"), reverse=True)[:20]:
        plan = json.loads(f.read_text(encoding="utf-8"))
        steps = plan.get("steps", [])
        done = sum(1 for s in steps if s.get("status") == "completed")
        plans.append({
            "plan_id": f.stem,
            "goal": plan.get("goal", "")[:60],
            "steps": f"{done}/{len(steps)}",
        })
    return json.dumps(plans, indent=2, ensure_ascii=False) if plans else "No plans found."


# ── Tool Executor ────────────────────────────────────────────────────────────

async def _run_tool(name: str, args: dict) -> str:
    fn = _TOOL_REGISTRY.get(name)
    if not fn:
        return f"Error: Unknown tool '{name}'"
    try:
        if asyncio.iscoroutinefunction(fn):
            result = await fn(**args)
        else:
            result = fn(**args)
            if inspect.iscoroutine(result):
                result = await result
        if result is None:
            return "OK (no return)"
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, ensure_ascii=False)
        return str(result)
    except Exception as e:
        return f"Error: {e}\n{traceback.format_exc()}"


@mcp.tool(
    name="agent_execute",
    description="Execute a specific step from a plan. Runs the tool and returns real output with execution memory."
)
async def agent_execute(plan_id: str, step_id: str) -> str:
    """
    Execute one step from a saved plan.

    Args:
        plan_id: Plan ID from agent_plan().
        step_id: Step ID (e.g., "step_1").
    """
    plan_path = PLANS_DIR / f"{plan_id}.json"
    if not plan_path.exists():
        return f"Error: Plan '{plan_id}' not found."
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for step in plan.get("steps", []):
        if step.get("id") == step_id:
            tool = step["tool"]
            args = step.get("args", {})
            step["status"] = "in_progress"
            step["attempts"] = step.get("attempts", 0) + 1
            step["started_at"] = datetime.now().isoformat()
            plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

            t0 = time.time()
            result = await _run_tool(tool, args)
            latency = time.time() - t0

            step["tool_latency"] = round(latency, 2)
            is_ok = not result.startswith("Error")
            step["status"] = "completed" if is_ok else "failed"
            if not is_ok:
                step["failure_reason"] = result[:300]
            step["result"] = result[:1000]
            plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

            meta = _TOOL_META.get(tool, {})
            line = (
                f"[{step_id}] {tool} ({latency:.1f}s) "
                f"→ {'OK' if is_ok else 'FAILED'}"
            )
            if meta.get("dangerous"):
                line = f"[WARN] dangerous tool: {line}"
            return f"{line}\n\n{result[:2000]}"
    return f"Error: Step '{step_id}' not found."


@mcp.tool(
    name="agent_execute_all",
    description="Execute all pending steps in a plan (parallel where possible). Returns all results."
)
async def agent_execute_all(plan_id: str) -> str:
    """
    Execute all pending steps in a plan.
    Uses parallel groups for independent steps.

    Args:
        plan_id: Plan ID from agent_plan().
    """
    plan_path = PLANS_DIR / f"{plan_id}.json"
    if not plan_path.exists():
        return f"Error: Plan '{plan_id}' not found."
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    graph = TaskGraph()
    step_map: dict[str, dict] = {}
    for step in plan.get("steps", []):
        step_map[step["id"]] = step
        graph.add_node(step["id"], {"tool": step["tool"]})
        for dep in step.get("depends_on", []):
            graph.add_dependency(step["id"], dep)

    logs = [f"Executing plan: {plan['goal']}"]
    overall_start = time.time()

    try:
        parallel_groups = graph.get_parallel_groups()
        logs.append(f"  Parallel groups: {len(parallel_groups)}")
    except ValueError:
        parallel_groups = [[s["id"] for s in plan.get("steps", [])]]
        logs.append("  (sequential fallback due to cycle)")

    for group in parallel_groups:
        pending = [sid for sid in group if step_map[sid].get("status") == "pending"]

        async def _run_step(sid: str) -> str:
            step = step_map[sid]
            if step.get("status") in ("completed", "failed"):
                return f"  SKIP {sid} ({step['status']})"
            tool = step["tool"]
            args = step.get("args", {})
            step["status"] = "in_progress"
            step["attempts"] = step.get("attempts", 0) + 1
            step["started_at"] = datetime.now().isoformat()
            plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

            t0 = time.time()
            result = await _run_tool(tool, args)
            latency = time.time() - t0

            step["tool_latency"] = round(latency, 2)
            is_ok = not result.startswith("Error")
            step["status"] = "completed" if is_ok else "failed"
            if not is_ok:
                step["failure_reason"] = result[:300]
            step["result"] = result[:1000]
            plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
            return f"  [{sid}] {tool} ({latency:.1f}s) → {'OK' if is_ok else 'FAILED'}"

        if len(pending) > 1:
            group_results = await asyncio.gather(*[_run_step(sid) for sid in pending])
            logs.extend(group_results)
        else:
            for sid in pending:
                logs.append(await _run_step(sid))

        for sid in group:
            step = step_map[sid]
            if step.get("status") in ("completed", "failed"):
                result_text = step.get("result", "")[:1200]
                logs.append(f"    {result_text}")

    total_time = time.time() - overall_start
    logs.append(f"\nTotal: {total_time:.1f}s")
    log_text = "\n".join(logs)
    log_file = LOGS_DIR / f"{plan_id}.log"
    log_file.write_text(log_text, encoding="utf-8")
    return log_text


# ── Auto Research (internal) ─────────────────────────────────────────────────

async def _auto_research(query: str, max_fetch: int = 3) -> str:
    """Search DDG + Firecrawl + auto-fetch top URLs. Gabungan semua source."""
    import requests
    from datetime import date
    from mcp_web import search_web

    ql = query.lower()
    if any(w in ql for w in ["hari ini", "today", "now"]):
        today = date.today().strftime("%d %B %Y")
        query = f"{query} {today}"
    if "trend" in ql and not any(w in ql for w in ["price", "harga", "kurs"]):
        query = f"{query} analysis outlook forecast"

    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")

    async def _fc_search():
        if not firecrawl_key:
            return ""
        try:
            r = await asyncio.to_thread(
                lambda: requests.post(
                    "https://api.firecrawl.dev/v1/search",
                    json={"query": query},
                    headers={"Authorization": f"Bearer {firecrawl_key}"},
                    timeout=15,
                )
            )
            if r.status_code != 200:
                return ""
            data = r.json().get("data", [])
            out = []
            for i, res in enumerate(data[:5], 1):
                t = res.get("title", "")
                s = res.get("description", "") or res.get("snippet", "")
                u = res.get("url", "")
                out.append(f"{i}. {t}\n   {s}\n   {u}")
            return "\n\n".join(out)
        except Exception:
            return ""

    ddg_result, fc_result = await asyncio.gather(
        search_web(query, max_results=5),
        _fc_search(),
    )

    combined = []
    if ddg_result and not ddg_result.startswith("(no search"):
        combined.append(f"-- DuckDuckGo --\n{ddg_result}")
    if fc_result:
        combined.append(f"-- Firecrawl --\n{fc_result}")

    parts = ["=== HASIL SEARCH ===", "\n\n".join(combined)]
    return "\n\n".join(parts)


# ── Final Registration ───────────────────────────────────────────────────────

_reg("auto_research", _auto_research, meta={
    "category": "research",
    "description": "Smart search + auto-fetch top URLs",
    "dangerous": False,
    "requires_repo": False,
    "requires_network": True,
    "timeout_suggestion": 20,
    "parallel_ok": True,
})

_register_all()

if __name__ == "__main__":
    mcp.run(transport="stdio")
