"""
mcp_planner.py — MCPKU Plan Generator
====================================
Generates DAG-based workflow plans from natural language goals.
Uses planner/ package for intent parsing, task graph, dependency solving.
"""

import json
import os
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from planner.intent_parser import parse_intent
from planner.task_graph import TaskGraph
from planner.dependency_solver import DependencySolver
from planner.execution_policy import ExecutionPolicy

mcp = FastMCP("planner")

@mcp.tool(
    name="plan_generate",
    description="Generate a JSON DAG workflow plan based on a user goal. "
    "Returns structured plan with parallel execution groups, dependency edges, "
    "and execution policies for each step."
)
async def plan_generate(goal: str, name: str, target_dir: str = "") -> str:
    """
    Args:
        goal: The end goal description (e.g. "research climate change and write a report").
        name: Name for the workflow plan.
        target_dir: Directory to save the plan JSON (default: %TEMP%\\mcpku\\plans).
    """
    # 1. Parse intent into structured tasks
    tasks = parse_intent(goal)
    if not tasks:
        return f"(error: could not parse any tasks from goal '{goal}')"

    # 2. Build DAG task graph
    graph = TaskGraph()
    for task in tasks:
        graph.add_node(
            task_id=task["id"],
            name=task["name"],
            tool=task.get("tool", ""),
            params=task.get("params", {}),
            depends_on=task.get("depends_on", []),
        )
    graph.topological_sort()

    # 3. Resolve dependencies and detect cycles
    solver = DependencySolver()
    cycles = solver.detect_cycles(graph)
    if cycles:
        return f"(error: circular dependency detected: {cycles})"

    # 4. Generate execution policy (parallel groups, retry, timeout)
    policy = ExecutionPolicy()
    parallel_groups = graph.get_parallel_groups()
    policy_blocks = {}
    for gid, group in enumerate(parallel_groups):
        for task_id in group:
            node = graph.get_node(task_id)
            if node:
                policy_blocks[task_id] = {
                    "parallel_group": gid,
                    "timeout_suggestion": policy.suggest_timeout(node.get("tool", "")),
                    "max_retries": policy.suggest_retries(node.get("tool", "")),
                    "parallel_ok": policy.can_parallel(node.get("tool", "")),
                }

    # 5. Build final plan
    plan = {
        "name": name,
        "goal": goal,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "version": 2,
        "total_tasks": len(tasks),
        "parallel_groups": len(parallel_groups),
        "tasks": tasks,
        "execution_order": [n["id"] for n in graph.get_ordered_nodes()],
        "parallel_groups_detail": [
            {"group": gid, "tasks": group}
            for gid, group in enumerate(parallel_groups)
        ],
        "policy": policy_blocks,
    }

    # 6. Save to file
    plans_dir = Path(target_dir) if target_dir else Path(tempfile.gettempdir()) / "mcpku" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    file_path = plans_dir / f"plan_{name}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    return json.dumps({
        "success": True,
        "plan_name": name,
        "path": str(file_path),
        "total_tasks": len(tasks),
        "parallel_groups": len(parallel_groups),
        "tasks": [t["name"] for t in tasks],
        "execution_order": plan["execution_order"],
    }, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")
