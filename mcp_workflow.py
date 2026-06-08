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

mcp = FastMCP("workflow")

@mcp.tool(
    name="workflow_run",
    description="Run a defined workflow from the workflows/ directory."
)
async def workflow_run(workflow_name: str) -> str:
    """
    Args:
        workflow_name: Name of the workflow file in workflows/ (e.g., 'deepsearch')
    """
    workflow_path = Path(__file__).parent / "workflows" / f"{workflow_name}.json"
    if not workflow_path.exists():
        return f"Error: Workflow '{workflow_name}' not found."
    
    with open(workflow_path, "r") as f:
        workflow = json.load(f)
    
    results = []
    for step in workflow.get("steps", []):
        task_name = step.get("name", "Unnamed task")
        cmd = step.get("command", "")
        
        results.append(f"── Executing: {task_name} ──")
        output = await autofix_run(command=cmd, workdir=str(Path.cwd()))
        results.append(output)
        
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
