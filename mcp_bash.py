import asyncio, shlex, os, re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bash", instructions="Execute shell commands. Use for running scripts, git, file operations, etc.")

# Command-level allowlist — cmd/powershell dihapus (terlalu berbahaya)
ALLOWED_COMMANDS = {
    "python", "pip", "git", "node", "npm", "npx",
    "dir", "ls", "echo", "type", "cat", "find", "grep",
    "mkdir", "rmdir", "copy", "move", "ren", "xcopy",
}

# Argument-level denylist: flag/pattern berbahaya lintas command
# Format: (regex_pattern, alasan)
DANGEROUS_ARG_PATTERNS = [
    # Windows destruktif
    (r"(?i)/f\s+/q",        "force+quiet delete flag"),
    (r"(?i)/s\s+/q",        "recursive quiet flag"),
    (r"(?i)del\b.*\*",      "wildcard delete"),
    (r"(?i)rmdir\b.*/s",    "recursive rmdir"),
    # Unix destruktif
    (r"-rf?\b",              "recursive force flag"),
    (r"--no-preserve-root",  "no-preserve-root flag"),
    # Redirection ke system paths
    (r">\s*/etc/",           "write to /etc"),
    (r">\s*C:\\Windows",     "write to C:\\Windows"),
    # Chained execution (injection)
    (r"[;&|`]\s*(rm|del|format|dd|mkfs|shutdown|reboot|curl|wget)\b", "chained dangerous command"),
    # Subshell / eval
    (r"\$\(.*\)",            "subshell substitution"),
    (r"`[^`]+`",             "backtick substitution"),
    # rm -rf / combinations
    (r"(?i)rm\b.*-[a-z]*r[a-z]*f",  "rm -rf variant"),
    (r"(?i)rm\b.*-[a-z]*f[a-z]*r",  "rm -fr variant"),
]

# Git: subcommand allowlist (lebih aman daripada allow semua argumen)
GIT_ALLOWED_SUBCOMMANDS = {
    "status", "log", "diff", "show", "branch", "remote",
    "fetch", "pull", "push", "add", "commit", "checkout",
    "stash", "tag", "clone", "init", "merge", "rebase",
    "reset", "restore", "ls-files", "shortlog", "describe",
}


def _check_command(command: str) -> str:
    """Return error string jika command tidak diizinkan, atau '' jika aman."""
    try:
        tokens = shlex.split(command, posix=(os.name != "nt"))
    except ValueError as e:
        return f"parse error: {e}"

    if not tokens:
        return "empty command"

    base = os.path.basename(tokens[0]).lower().rstrip(".exe")

    if base not in ALLOWED_COMMANDS:
        return f"command '{tokens[0]}' not in allowed list"

    # Git: cek subcommand
    if base == "git":
        if len(tokens) < 2:
            return "git: subcommand required"
        sub = tokens[1].lower()
        if sub not in GIT_ALLOWED_SUBCOMMANDS:
            return f"git subcommand '{sub}' not allowed"

    # Argument-level denylist — cek seluruh command string
    for pattern, reason in DANGEROUS_ARG_PATTERNS:
        if re.search(pattern, command):
            return f"blocked dangerous pattern: {reason}"

    return ""


@mcp.tool(
    name="run_command",
    description="Jalankan perintah shell yang diizinkan. Gunakan untuk operasi file, git, script."
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
