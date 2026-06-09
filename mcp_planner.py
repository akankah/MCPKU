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
from planner.intent_parser import parse_goal as parse_intent
from planner.task_graph import TaskGraph
from planner.dependency_solver import resolve_dependencies, Dependency
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

    # 2. Resolve dependencies between intents
    deps = resolve_dependencies(tasks)
    
    # 3. Build DAG task graph
    graph = TaskGraph()
    # Add nodes for each task
    for i, task in enumerate(tasks):
        # Generate a unique task ID
        task_id = f"{task.action}_{i}"
        # Map Intent to task structure
        graph.add_node(
            node_id=task_id,
            data={
                "name": task.target or task.action,
                "tool": task.action,  # Assume action maps to tool name
                "params": task.params.copy(),  # Make a copy to avoid modifying original
                "depends_on": []  # Will be filled in based on dependencies
            }
        )
    
    # Add edges based on resolved dependencies
    for dep in deps:
        # Find indices of the from_action and to_action in tasks
        from_indices = [i for i, t in enumerate(tasks) if t.action == dep.from_action]
        to_indices = [i for i, t in enumerate(tasks) if t.action == dep.to_action]
        
        # Add edges from all from_action instances to all to_action instances
        # (This creates a complete bipartite graph between the action types)
        for from_idx in from_indices:
            from_task_id = f"{tasks[from_idx].action}_{from_idx}"
            for to_idx in to_indices:
                to_task_id = f"{tasks[to_idx].action}_{to_idx}"
                graph.add_dependency(from_task_id, to_task_id)
    
    # 4. Check for cycles
    try:
        graph.topological_sort()
    except ValueError as e:
        if "TaskGraph has a cycle" in str(e):
            return f"(error: circular dependency detected in task graph)"
        else:
            return f"(error: {str(e)})"

    # 5. Generate execution policy (parallel groups, retry, timeout)
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

    # 6. Build final plan
    plan = {
        "name": name,
        "goal": goal,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "version": 2,
        "total_tasks": len(tasks),
        "parallel_groups": len(parallel_groups),
        "tasks": [
            {
                "id": f"{task.action}_{i}",
                "name": task.target or task.action,
                "tool": task.action,
                "params": task.params
            }
            for i, task in enumerate(tasks)
        ],
        "execution_order": [f"{task.action}_{i}" for i, task in enumerate(graph.get_ordered_nodes())],
        "parallel_groups_detail": [
            {"group": gid, "tasks": [f"{tasks[i].action}_{i}" for i in group_indices]}
            for gid, group_indices in enumerate([[i for i, t in enumerate(tasks) if f"{t.action}_{i}" in group] for group in parallel_groups])
        ],
        "policy": policy_blocks,
    }

    # 7. Save to file
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
        "tasks": [f"{task.action}_{i}" for i, task in enumerate(tasks)],
        "execution_order": plan["execution_order"],
    }, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")
