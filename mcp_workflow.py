"""
mcp_workflow.py — MCPKU Workflow Orchestrator
=============================================
Orchestrates autonomous tasks using a DAG (Directed Acyclic Graph) approach.
- Uses existing MCPKU servers (bash, filesystem, autofix, etc.)
- Uses memory for state persistence and resume-capability
- Uses autofix loop for self-healing execution
"""

import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp_autofix import autofix_run
from mcp_state import state_init, state_update

mcp = FastMCP("workflow")

@mcp.tool(
    name="workflow_run",
    description="Run a defined workflow from a specific directory."
)
async def workflow_run(workflow_id: str, workflow_name: str, workflow_dir: str) -> str:
    """
    Args:
        workflow_id: Unique ID for this execution.
        workflow_name: Name of the workflow (without .json extension).
        workflow_dir: The directory containing the workflow JSON file.
    """
    workflow_path = Path(workflow_dir) / f"{workflow_name}.json"
    if not workflow_path.exists():
        return f"Error: Workflow '{workflow_name}.json' not found in {workflow_dir}"
    
    with open(workflow_path, "r") as f:
        workflow = json.load(f)
    
    # Load history for resume (check state in target_dir)
    completed_steps = set()
    state_file = Path(workflow_dir) / "workflow_state.jsonl"
    if state_file.exists():
        with open(state_file, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("status") == "completed":
                    completed_steps.add(entry.get("step_id"))

    # Initialize state only if not resuming
    if not completed_steps:
        await state_init(workflow_id, json.dumps(workflow))
    
    results = []
    for step in workflow.get("steps", []):
        step_id = step.get("id", "unknown")
        
        if step_id in completed_steps:
            results.append(f"── Skipping: {step.get('name')} (already completed) ──")
            continue

        task_name = step.get("name", "Unnamed task")
        cmd = step.get("command", "")
        
        # Track start
        await state_update(workflow_id, step_id, "in_progress")
        
        results.append(f"── Executing: {task_name} ──")
        # Use target workflow_dir as working dir for autofix
        output = await autofix_run(command=cmd, workdir=workflow_dir)
        results.append(output)
        
        # Check success
        if "✅ Command succeeded" in output:
            await state_update(workflow_id, step_id, "completed", verification="Success")
        else:
            await state_update(workflow_id, step_id, "failed", error_info=output[-500:])
            results.append("⚠️ Task failed, halting workflow.")
            break
        
    return "\n".join(results)

@mcp.tool(
    name="workflow_generate",
    description="Generate a new workflow plan based on a user goal."
)
async def workflow_generate(goal: str) -> str:
    """
    Generates a task graph for a goal and saves it to workflows/
    """
    # Placeholder: AI plan generation logic
    return "Plan generated. (Generator in development)"

if __name__ == "__main__":
    mcp.run(transport="stdio")
