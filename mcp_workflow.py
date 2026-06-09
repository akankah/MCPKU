"""
mcp_workflow.py — MCPKU Workflow Runtime (DAG-based)
====================================================
Autonomous execution engine using a Directed Acyclic Graph approach.
- DAG scheduler with topological sort + parallel groups
- Retry with backoff per step
- Context/artifact passing between steps
- Structured event logging
- Resume capability via workflow_state.jsonl
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp_autofix import autofix_run
from planner.task_graph import TaskGraph

mcp = FastMCP("workflow")


def _schema() -> dict:
    return {
        "schema_version": "2.0",
        "workflow": {
            "id": "str (required)",
            "name": "str (required)",
            "description": "str (optional)",
            "steps": [
                {
                    "id": "str (required, unique)",
                    "name": "str (required)",
                    "tool": "str (default: bash_run_command)",
                    "args": "dict (tool arguments, supports {query} and {outputs.step_id.key})",
                    "depends_on": ["str (step IDs this step depends on)"],
                    "retry": "int (default: 0, max retries on failure)",
                    "retry_delay": "float (default: 2.0, seconds between retries)",
                    "timeout": "int (default: 60, seconds)",
                    "outputs": {"key": "value (named outputs, stored in context)"},
                    "validate": {
                        "command": "str (validation command, must exit clean)",
                        "retry": "int (validation retries)"
                    }
                }
            ]
        }
    }


def _resolve_refs(text: str, context: dict, query: str) -> str:
    """Resolve {query} and {outputs.step_id.key} placeholders."""

    def _replace(m):
        full = m.group(1)
        if full == "query":
            return query
        if full.startswith("outputs."):
            parts = full.split(".")
            if len(parts) >= 3:
                step_id = parts[1]
                key = ".".join(parts[2:])
                outputs = context.get("outputs", {}).get(step_id, {})
                val = outputs.get(key, m.group(0))
                if isinstance(val, str):
                    return val
                return json.dumps(val, ensure_ascii=False) if val is not None else m.group(0)
        return m.group(0)

    return re.sub(r"\{([^}]+)\}", _replace, text)


def _load_state(workflow_dir: str) -> dict[str, str]:
    """Load completed steps from workflow_state.jsonl for resume."""
    completed = {}
    state_file = Path(workflow_dir) / "workflow_state.jsonl"
    if not state_file.exists():
        return completed
    with open(state_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            sid = entry.get("step_id", "")
            if entry.get("status") == "completed":
                completed[sid] = "completed"
            elif entry.get("status") == "failed":
                completed[sid] = "failed"
    return completed


def _append_event(workflow_dir: str, event: dict):
    """Append structured event to workflow_state.jsonl."""
    event["timestamp"] = datetime.now().isoformat()
    state_file = Path(workflow_dir) / "workflow_state.jsonl"
    with open(state_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


@mcp.tool(
    name="workflow_run",
    description="Run a DAG workflow from a JSON file. Supports resume, parallel groups, retry, and artifact passing."
)
async def workflow_run(
    workflow_id: str,
    workflow_name: str,
    workflow_dir: str,
    query: str = ""
) -> str:
    """
    Args:
        workflow_id: Unique ID for this execution.
        workflow_name: Workflow filename (without .json).
        workflow_dir: Directory containing the workflow JSON.
        query: Optional query for {query} placeholders.
    """
    workflow_path = Path(workflow_dir) / f"{workflow_name}.json"
    if not workflow_path.exists():
        return f"Error: Workflow '{workflow_name}.json' not found in {workflow_dir}"

    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)

    steps_data = workflow.get("steps", [])
    if not steps_data:
        return "Error: Workflow has no steps."

    state = _load_state(workflow_dir)
    graph = TaskGraph()
    step_map: dict[str, dict] = {}

    for s in steps_data:
        sid = s.get("id", "unknown")
        step_map[sid] = s
        graph.add_node(sid)
        for dep in s.get("depends_on", []):
            graph.add_dependency(sid, dep)

    if graph.has_cycle():
        return "Error: Workflow has a cycle. Aborting."

    context: dict[str, Any] = {
        "workflow_id": workflow_id,
        "outputs": {},
        "query": query,
    }

    _append_event(workflow_dir, {
        "type": "workflow.started",
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "steps": len(steps_data),
    })

    logs = [f"Workflow: {workflow.get('name', workflow_name)} ({workflow_id})"]
    logs.append(f"Steps: {len(steps_data)}, Resume: {len(state)} completed")

    try:
        parallel_groups = graph.get_parallel_groups()
    except ValueError:
        parallel_groups = [[s["id"] for s in steps_data]]

    overall_start = time.time()
    halted = False

    for group in parallel_groups:
        if halted:
            break
        async def _exec_step(sid: str) -> str:
            step = step_map[sid]
            name = step.get("name", sid)
            tool = step.get("tool", "bash_run_command")
            args = dict(step.get("args", {}))
            retry_count = step.get("retry", 0)
            retry_delay = step.get("retry_delay", 2.0)
            validate_cfg = step.get("validate", {})

            if state.get(sid) == "completed":
                return f"  SKIP [{sid}] {name} (already completed)"

            if state.get(sid) == "failed":
                return f"  SKIP [{sid}] {name} (previously failed)"

            # Resolve placeholders in args
            for k, v in args.items():
                if isinstance(v, str):
                    args[k] = _resolve_refs(v, context, query)

            logs_step = [f"  ▶ [{sid}] {name} (tool={tool})"]

            for attempt in range(retry_count + 1):
                logs_step.append(f"    attempt {attempt + 1}/{retry_count + 1}")
                _append_event(workflow_dir, {
                    "type": "step.started",
                    "workflow_id": workflow_id,
                    "step_id": sid,
                    "attempt": attempt + 1,
                })

                t0 = time.time()
                output = await autofix_run(command=args.get("command", ""), workdir=str(workflow_dir))
                latency = time.time() - t0

                is_success = "✅ Command succeeded" in output

                # Validation
                if is_success and validate_cfg.get("command"):
                    val_cmd = _resolve_refs(validate_cfg["command"], context, query)
                    logs_step.append(f"    validating: {val_cmd[:60]}")
                    val_output = await autofix_run(command=val_cmd, workdir=str(workflow_dir))
                    if "✅ Command succeeded" not in val_output:
                        is_success = False
                        logs_step.append("    ⚠️  Validation failed")
                    else:
                        logs_step.append("    ✓ Validation passed")

                _append_event(workflow_dir, {
                    "type": "step.completed" if is_success else "step.failed",
                    "workflow_id": workflow_id,
                    "step_id": sid,
                    "attempt": attempt + 1,
                    "latency": round(latency, 2),
                })

                if is_success:
                    context.setdefault("outputs", {})[sid] = {
                        "result": output[:1000],
                        "latency": round(latency, 2),
                    }
                    # Store named outputs
                    named_outputs = step.get("outputs", {})
                    if named_outputs:
                        context["outputs"][sid].update(named_outputs)

                    logs_step.append(f"    ✓ OK ({latency:.1f}s)")
                    logs_step.append(f"    {output[:600]}")
                    break
                else:
                    if attempt < retry_count:
                        wait = retry_delay * (2 ** attempt)
                        logs_step.append(f"    ✗ Failed, retry in {wait:.0f}s")
                        await asyncio.sleep(wait)
                    else:
                        logs_step.append(f"    ✗ Failed after {retry_count + 1} attempts")
                        logs_step.append(f"    {output[:600]}")
                        _append_event(workflow_dir, {
                            "type": "step.exhausted",
                            "workflow_id": workflow_id,
                            "step_id": sid,
                            "error": output[:500],
                        })

            return "\n".join(logs_step)

        pending = [sid for sid in group if state.get(sid) not in ("completed", "failed")]

        if len(pending) > 1:
            group_results = await asyncio.gather(*[_exec_step(sid) for sid in pending])
            logs.extend(group_results)
        else:
            for sid in pending:
                logs.append(await _exec_step(sid))

        # Check for cascade failures in this group
        for sid in group:
            if any(f"[{sid}]" in l and "Failed after" in l for l in logs):
                logs.append(f"\n  ⛔ Cascade halt: step [{sid}] failed, stopping.")
                _append_event(workflow_dir, {
                    "type": "workflow.halted",
                    "workflow_id": workflow_id,
                    "reason": f"Step {sid} failed",
                })
                halted = True
                break

    total_time = time.time() - overall_start
    logs.append(f"\nTotal: {total_time:.1f}s")

    _append_event(workflow_dir, {
        "type": "workflow.completed",
        "workflow_id": workflow_id,
        "duration": round(total_time, 2),
        "artifacts": context.get("outputs", {}),
    })

    return "\n".join(logs)


@mcp.tool(
    name="workflow_generate",
    description="Generate a DAG workflow plan from a goal using planner intelligence."
)
async def workflow_generate(goal: str) -> str:
    """
    Generate a structured DAG workflow from a natural-language goal.

    Args:
        goal: Description of what the workflow should do.
    """
    from planner.intent_parser import parse_goal
    from planner.dependency_solver import resolve_dependencies, order_by_dependencies

    intents = parse_goal(goal)
    deps = resolve_dependencies(intents)
    ordered = order_by_dependencies(intents, deps)

    TOOL_MAP = {
        "research": {"tool": "bash_run_command", "args": {"command": "python -c \"print('research: {query}')\""}},
        "memory": {"tool": "bash_run_command", "args": {"command": "python -c \"print('memory: {query}')\""}},
        "debug": {"tool": "autofix_run", "args": {"command": "echo 'debug: {query}'"}},
        "git": {"tool": "bash_run_command", "args": {"command": "git status"}},
        "files": {"tool": "bash_run_command", "args": {"command": "ls -la"}},
        "time": {"tool": "bash_run_command", "args": {"command": "python -c \"from datetime import datetime; print(datetime.now())\""}},
    }

    action_list = [x.action for x in ordered]
    steps = []
    for i, intent in enumerate(ordered):
        tmpl = TOOL_MAP.get(intent.action, {"tool": "bash_run_command", "args": {"command": "echo '{query}'"}})
        step = {
            "id": f"step_{i + 1}",
            "name": intent.action.title(),
            "tool": tmpl["tool"],
            "args": dict(tmpl["args"]),
            "depends_on": [],
            "retry": 1,
            "retry_delay": 2.0,
            "timeout": 60,
            "outputs": {},
        }
        for d in deps:
            if d.to_action == intent.action and d.from_action in action_list:
                from_idx = action_list.index(d.from_action)
                step["depends_on"].append(f"step_{from_idx + 1}")
        steps.append(step)

    workflow = {
        "schema_version": "2.0",
        "id": goal.lower().replace(" ", "_")[:30],
        "name": goal[:60],
        "description": f"Auto-generated workflow for: {goal}",
        "steps": steps,
    }

    # Save to workflows/
    wf_dir = Path("workflows")
    wf_dir.mkdir(exist_ok=True)
    wf_name = goal.lower().replace(" ", "_")[:30]
    wf_path = wf_dir / f"{wf_name}.json"
    wf_path.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")

    return json.dumps({"workflow_id": workflow["id"], "file": str(wf_path), "steps": len(steps)}, indent=2, ensure_ascii=False)


@mcp.tool(
    name="workflow_schema",
    description="Return the current workflow JSON schema specification."
)
async def workflow_schema() -> str:
    """Return the workflow schema spec for reference."""
    return json.dumps(_schema(), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
