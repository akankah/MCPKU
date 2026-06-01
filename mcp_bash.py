import asyncio, shlex, os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bash", instructions="Execute shell commands. Use for running scripts, git, file operations, etc.")

ALLOWED_COMMANDS = [
    "python", "pip", "git", "node", "npm", "npx", "cmd", "powershell",
    "dir", "ls", "cd", "echo", "type", "cat", "find", "grep",
    "mkdir", "rmdir", "del", "copy", "move", "ren", "xcopy",
]

def _check_command(command: str) -> str:
    tokens = shlex.split(command, posix=False)
    if not tokens:
        return "empty command"
    base = os.path.basename(tokens[0]).lower().rstrip(".exe")
    if base not in ALLOWED_COMMANDS:
        return f"command '{tokens[0]}' not in allowed list"
    return ""

@mcp.tool(
    name="run_command",
    description="Jalankan perintah shell. Gunakan untuk operasi file, git, script, dll."
)
async def run_command(command: str, timeout: int = 30, workdir: str = "") -> str:
    if not command.strip():
        return "(empty command)"
    denied = _check_command(command)
    if denied:
        return f"(denied: {denied})"
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir or os.getcwd(),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        result = ""
        if out:
            result += f"[stdout]\n{out[:5000]}"
        if err:
            if result:
                result += "\n"
            result += f"[stderr]\n{err[:2000]}"
        if not result:
            result = f"(exit code: {proc.returncode}, no output)"
        else:
            result += f"\n(exit code: {proc.returncode})"
        return result
    except asyncio.TimeoutError:
        return f"(timeout after {timeout}s)"
    except Exception as e:
        return f"(error: {e})"

if __name__ == "__main__":
    mcp.run(transport="stdio")
