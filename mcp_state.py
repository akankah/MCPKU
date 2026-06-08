"""
mcp_state.py — Workflow State Board
===================================
Tracks workflow execution status in JSONL per project.
Acts as a 'Black Box Recorder' for autonomous agents.
"""

import json
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("state")

def _get_state_file(cwd: str = "") -> Path:
    # Mengikuti logic error_kb: simpan di <cwd>/state.jsonl
    base = Path(cwd).resolve() if cwd else Path.cwd()
    return base / "workflow_state.jsonl"

@mcp.tool(
    name="state_init", 
    description="Initialize a new workflow session with a task plan."
)
async def state_init(workflow_id: str, plan: str) -> str:
    """
    Args:
        workflow_id: Unique identifier for the workflow session.
        plan: JSON string of the task graph/plan.
    """
    state_file = _get_state_file()
    entry = {
        "type": "init",
        "workflow_id": workflow_id,
        "timestamp": datetime.now().isoformat(),
        "plan": plan
    }
    with open(state_file, "w") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Workflow {workflow_id} initialized."

@mcp.tool(
    name="state_update", 
    description="Update a workflow step status with optional error or verification info."
)
async def state_update(
    workflow_id: str, 
    step_id: str, 
    status: str, 
    attempt: int = 1,
    error_info: str = "",
    verification: str = ""
) -> str:
    """
    Args:
        status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'rolled_back'
        error_info: JSON string of error details if status is 'failed'
        verification: JSON string of verification results if status is 'completed'
    """
    state_file = _get_state_file()
    entry = {
        "workflow_id": workflow_id,
        "step_id": step_id,
        "status": status,
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
        "error_info": error_info,
        "verification": verification
    }
    with open(state_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Step {step_id} status updated to {status}."

if __name__ == "__main__":
    mcp.run(transport="stdio")
