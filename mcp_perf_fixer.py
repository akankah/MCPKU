import json
import re
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("perf_fixer", instructions="""
Performance Fixer Bridge: Connects API Performance Tester results to Auto-Fix.
It identifies performance bottlenecks and suggests optimization strategies.
""")

@mcp.tool(name="analyze_performance_report", description="Analyze output from mcp_api_tester and trigger optimization suggestions.")
async def analyze_performance_report(report_json: str, threshold_ms: int = 200) -> str:
    """Analyzes performance report and categorizes results for optimization."""
    try:
        data = json.loads(report_json)
        latency = data.get("avg_latency_ms", 0)
        url = data.get("url", "unknown")
        
        lines = [f"── Performance Analysis for {url} ──"]
        
        if latency > threshold_ms:
            lines.append(f"❌ Latency ({latency}ms) exceeds threshold ({threshold_ms}ms).")
            lines.append("\n[Recommended Fixes]")
            
            # Simple heuristic optimization logic
            if "localhost" in url or "127.0.0.1" in url:
                lines.append("- Optimization (Backend): Check database queries, implement caching (Redis), or optimize loops.")
            else:
                lines.append("- Optimization (Network/Frontend): Check CDN usage, minimize payload size, or optimize SSL handshake.")
            
            # Return as a specialized error classification that autofix can recognize if we integrate it
            lines.append("\nSuggested Action: Use 'autofix_run' with optimization scripts or profiling tools.")
        else:
            lines.append(f"✅ Latency ({latency}ms) is within healthy limits.")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error analyzing report: {str(e)}"

@mcp.tool(name="bridge_to_autofix", description="Directly trigger an optimization task based on high latency.")
async def bridge_to_autofix(url: str, latency_ms: float) -> str:
    """Generates a pseudo-error message that can be fed into autofix_run for optimization."""
    error_msg = f"Performance.HighLatency: Endpoint {url} responded with {latency_ms}ms"
    return (
        f"Generated Optimization Trigger:\\n\\n{error_msg}\\n\\n"
        f"Instruction: Call 'autofix_run' with a profiling command (e.g., 'pytest --profile') to fix this."
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")
