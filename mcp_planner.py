"""
mcp_planner.py — MCPKU Plan Generator
====================================
Generates JSON workflows from natural language goals.
"""

from mcp.server.fastmcp import FastMCP
import json
from pathlib import Path
from mcp_memory import search_nodes, create_entities

mcp = FastMCP("planner")

@mcp.tool(
    name="plan_generate",
    description="Generate a JSON workflow plan based on a user goal."
)
async def plan_generate(goal: str, name: str) -> str:
    """
    Args:
        goal: The end goal.
        name: The name for the workflow.
    """
    # 1. Search memory for similar templates
    existing = await search_nodes(goal)
    memory_info = f"Found {len(existing)} similar templates in memory." if existing else "No existing templates found."
    
    # 2. Plan generation (Placeholder for LLM call)
    plan = {
        "name": name,
        "goal": goal,
        "steps": [
            { "id": "step1", "name": "Init", "command": f"echo 'Starting {name}'" },
            { "id": "step2", "name": "Execution", "command": "echo 'Run logic here'" }
        ]
    }
    
    # 3. Save to workflows/
    workflow_dir = Path(__file__).parent / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    file_path = workflow_dir / f"{name}.json"
    with open(file_path, "w") as f:
        json.dump(plan, f, indent=2)
        
    # 4. Save to Memory
    await create_entities([{
        "name": name,
        "entityType": "workflow_template",
        "observations": [f"Goal: {goal}", f"Path: {file_path}"]
    }])
        
    return f"Workflow plan '{name}' generated at {file_path}. {memory_info}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
