import os
import sys
import json
import psutil
import platform
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sysmon", instructions="""
Advanced System Monitor Server: Monitor CPU, RAM, Disk, and Processes.
Helps in debugging performance issues and resource leaks.
""")

@mcp.tool(name="get_system_stats", description="Get overall system resource usage (CPU, RAM, Disk).")
async def get_system_stats() -> str:
    \"\"\"Returns a summary of current system resource usage.\"\"\"
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        stats = {
            "timestamp": datetime.now().isoformat(),
            "os": f"{platform.system()} {platform.release()}",
            "cpu_percent": cpu_usage,
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_percent": disk.percent
            }
        }
        return json.dumps(stats, indent=2)
    except Exception as e:
        return f"Error gathering stats: {str(e)}"

@mcp.tool(name="list_top_processes", description="List top N processes by CPU or Memory usage.")
async def list_top_processes(sort_by: str = "cpu", limit: int = 10) -> str:
    \"\"\"List top processes. sort_by can be 'cpu' or 'memory'.\"\"\"
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        key = 'cpu_percent' if sort_by.lower() == "cpu" else 'memory_percent'
        sorted_procs = sorted(processes, key=lambda x: x[key], reverse=True)[:limit]
        
        return json.dumps(sorted_procs, indent=2)
    except Exception as e:
        return f"Error listing processes: {str(e)}"

@mcp.tool(name="kill_process", description="Kill a process by PID.")
async def kill_process(pid: int) -> str:
    \"\"\"Attempts to terminate a process with the given PID.\"\"\"
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        return f"Process {name} (PID: {pid}) has been terminated."
    except psutil.NoSuchProcess:
        return f"Error: No process found with PID {pid}."
    except psutil.AccessDenied:
        return f"Error: Permission denied to kill process {pid}."
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
