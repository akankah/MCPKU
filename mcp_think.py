from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sequential-thinking", instructions="""
Sequential thinking tool for structured reasoning.
Use when you need to break down complex problems step by step.
Each call records a thought step. The model should use this iteratively.
""")

THOUGHTS = []

@mcp.tool(
    name="think",
    description="Rekam langkah pemikiran untuk reasoning bertahap. Gunakan untuk masalah kompleks."
)
async def think(thought: str, step_number: int = 0) -> str:
    if not thought.strip():
        return "(empty thought)"
    step = step_number if step_number > 0 else len(THOUGHTS) + 1
    entry = {"step": step, "thought": thought.strip()}
    THOUGHTS.append(entry)
    history = "\n".join(f"Step {t['step']}: {t['thought']}" for t in THOUGHTS)
    return f"Thought recorded as step {step}.\n\nCurrent thought chain:\n{history}"

@mcp.tool(
    name="reset_thinking",
    description="Reset rantai pemikiran dan mulai dari awal"
)
async def reset_thinking() -> str:
    THOUGHTS.clear()
    return "Thought chain reset."

if __name__ == "__main__":
    mcp.run(transport="stdio")
