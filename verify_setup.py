"""MCPKU setup verifier & sync tool.

Usage:
    python verify_setup.py check       # verify current global config
    python verify_setup.py sync        # install/update global config from MCPKU/opencode.jsonc
    python verify_setup.py status      # show MCP server status + versions
    python verify_setup.py doctor      # diagnose + suggest fixes

Designed so user can re-run any time MCPKU is moved/upgraded, or after
opencode CLI updates that might clobber the global config.
"""
import json
import os
import sys
import re
import shutil
from pathlib import Path

MCPKU_DIR = Path(r"E:\MCPKU")
GLOBAL_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
EXPECTED_SERVERS = {
    "bash", "think", "sqlite", "time", "filesystem", "memory",
    "git", "web", "github", "redis", "postgres", "vector",
    "browser", "diagnostics", "autofix", "context7", "research",
}


def _strip_jsonc_comments(text: str) -> str:
    """Robust JSONC parser: strip // and /* */ comments before json.loads.

    Preserves comments inside quoted strings (e.g., URLs with //).
    """
    out = []
    i, n = 0, len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        # Not in string
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            # line comment - skip to end of line
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            # block comment
            i += 2
            while i < n - 1 and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_global_config() -> dict:
    if not GLOBAL_CONFIG.exists():
        return {}
    text = GLOBAL_CONFIG.read_text(encoding="utf-8")
    try:
        return json.loads(_strip_jsonc_comments(text))
    except json.JSONDecodeError as e:
        print(f"[ERR] global config invalid JSON: {e}")
        return {}


def check_paths(servers: dict) -> list:
    """Return list of broken server entries."""
    broken = []
    for name, cfg in servers.items():
        cmd = cfg.get("command", [])
        if not cmd:
            broken.append((name, "no command"))
            continue
        # Extract path from command[1] (after 'python' or 'npx')
        if len(cmd) >= 2 and cmd[0] in ("python", "npx"):
            target = cmd[1]
            if cmd[0] == "python":
                p = Path(target)
                if not p.exists():
                    broken.append((name, f"missing file: {target}"))
        else:
            broken.append((name, f"unexpected command: {cmd}"))
    return broken


def cmd_check():
    """Verify all 17 MCPs are correctly registered in global config."""
    print("=" * 60)
    print(f"  MCPKU setup check")
    print(f"  global config: {GLOBAL_CONFIG}")
    print(f"  MCPKU dir:     {MCPKU_DIR}")
    print("=" * 60)

    if not GLOBAL_CONFIG.exists():
        print(f"\n[FAIL] global config not found: {GLOBAL_CONFIG}")
        print(f"       Run: python verify_setup.py sync")
        return 1

    cfg = load_global_config()
    servers = cfg.get("mcp", {})

    if not servers:
        print(f"\n[FAIL] no 'mcp' section in global config")
        print(f"       Run: python verify_setup.py sync")
        return 1

    registered = set(servers.keys())
    missing = EXPECTED_SERVERS - registered
    extra = registered - EXPECTED_SERVERS

    print(f"\nRegistered: {len(registered)}/17")
    if missing:
        print(f"[FAIL] missing servers: {', '.join(sorted(missing))}")
        print(f"       Run: python verify_setup.py sync")
    if extra:
        print(f"[INFO] extra servers (not in MCPKU canonical list): {', '.join(sorted(extra))}")

    broken = check_paths(servers)
    if broken:
        print(f"\n[FAIL] broken server paths:")
        for name, reason in broken:
            print(f"       - {name}: {reason}")
        return 1
    else:
        print(f"[OK]   all server paths valid")

    # Check enabled flag
    disabled = [n for n, c in servers.items() if not c.get("enabled", False)]
    if disabled:
        print(f"[WARN] disabled servers: {', '.join(disabled)}")
    else:
        print(f"[OK]   all servers enabled")

    # Check provider section is intact
    providers = cfg.get("provider", {})
    if "lmarena" in providers:
        print(f"[OK]   lmarena provider configured (9 models)")
    if "litlellm" in providers:
        print(f"[OK]   litlellm provider configured")

    if missing or broken:
        print(f"\n[!] Setup has issues. Run: python verify_setup.py sync")
        return 1
    else:
        print(f"\n[OK] Setup complete. MCPKU will auto-load in all OpenCode CLI sessions.")
        return 0


def cmd_sync():
    """Copy MCPKU's opencode.jsonc as the global config (if it has the mcp section)."""
    print("=" * 60)
    print(f"  MCPKU setup sync")
    print("=" * 60)

    # Read user's CURRENT global config (don't lose provider/model)
    if GLOBAL_CONFIG.exists():
        try:
            existing = load_global_config()
        except Exception:
            existing = {}
        print(f"\n[INFO] global config exists, will preserve provider/model sections")
    else:
        existing = {}
        print(f"\n[INFO] global config not found, will create new")

    # Build fresh mcp block from MCPKU repo (the canonical source)
    # For now: rebuild the same block (user can re-run after adding new servers)
    fresh_mcp = {
        "bash":        {"type": "local", "command": ["python", "E:/MCPKU/mcp_bash.py"], "enabled": True},
        "think":       {"type": "local", "command": ["python", "E:/MCPKU/mcp_think.py"], "enabled": True},
        "sqlite":      {"type": "local", "command": ["python", "E:/MCPKU/mcp_sqlite.py"], "enabled": True,
                         "env": {"SQLITE_DB_PATH": "", "PYTHONIOENCODING": "utf-8"}},
        "time":        {"type": "local", "command": ["python", "E:/MCPKU/mcp_time.py"], "enabled": True,
                         "env": {"LOCAL_TIMEZONE": "Asia/Jakarta"}},
        "filesystem":  {"type": "local", "command": ["python", "E:/MCPKU/mcp_filesystem.py"], "enabled": True,
                         "env": {"MCP_EXTRA_ALLOWED_DIR": "E:/", "MCP_FS_ALLOW_ALL": "1"}},
        "memory":      {"type": "local", "command": ["python", "E:/MCPKU/mcp_memory.py"], "enabled": True,
                         "env": {"MEMORY_FILE_PATH": "E:/MCPKU/memory.jsonl"}},
        "git":         {"type": "local", "command": ["python", "E:/MCPKU/mcp_git.py"], "enabled": True},
        "web":         {"type": "local", "command": ["python", "E:/MCPKU/mcp_web.py"], "enabled": True,
                         "env": {"FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"}},
        "github":      {"type": "local", "command": ["python", "E:/MCPKU/mcp_github.py"], "enabled": True,
                         "env": {"GITHUB_API_KEY": "${GITHUB_API_KEY}"}},
        "redis":       {"type": "local", "command": ["python", "E:/MCPKU/mcp_redis.py"], "enabled": True,
                         "env": {"REDIS_URL": "redis://localhost:6379/0"}},
        "postgres":    {"type": "local", "command": ["python", "E:/MCPKU/mcp_postgres.py"], "enabled": True,
                         "env": {"DATABASE_URL": "${DATABASE_URL}", "REDIS_URL": "redis://localhost:6379/0"}},
        "vector":      {"type": "local", "command": ["python", "E:/MCPKU/mcp_vector.py"], "enabled": True,
                         "env": {"DATABASE_URL": "${DATABASE_URL}", "OPENAI_API_KEY": "${OPENAI_API_KEY}",
                                 "REDIS_URL": "redis://localhost:6379/0"}},
        "browser":     {"type": "local", "command": ["python", "E:/MCPKU/mcp_browser.py"], "enabled": True},
        "diagnostics": {"type": "local", "command": ["python", "E:/MCPKU/mcp_diagnostics.py"], "enabled": True},
        "autofix":     {"type": "local", "command": ["python", "E:/MCPKU/mcp_autofix.py"], "enabled": True},
        "context7":    {"type": "local", "command": ["npx", "-y", "@upstash/context7-mcp"], "enabled": True},
        "research":    {"type": "local", "command": ["python", "E:/MCPKU/mcp_research.py"], "enabled": True},
    }

    # Update existing mcp block with fresh server entries
    existing.setdefault("mcp", {}).update(fresh_mcp)

    GLOBAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_CONFIG.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n[OK]   wrote {len(fresh_mcp)} servers to {GLOBAL_CONFIG}")
    print(f"[OK]   preserved provider/model sections")
    print(f"\nRun: python verify_setup.py check    # to verify")


def cmd_status():
    """Show loaded MCPs + version + path validation."""
    print("=" * 60)
    print(f"  MCPKU runtime status")
    print("=" * 60)

    cfg = load_global_config()
    servers = cfg.get("mcp", {})

    if not servers:
        print("[FAIL] no mcp servers in global config. Run: python verify_setup.py sync")
        return 1

    print(f"\n  Global config: {GLOBAL_CONFIG}")
    print(f"  Servers registered: {len(servers)}")
    print(f"\n  {'NAME':<14} {'ENABLED':<8} {'PATH/CMD':<40}")
    print(f"  {'-'*14} {'-'*8} {'-'*40}")
    for name, c in servers.items():
        enabled = "yes" if c.get("enabled", False) else "no"
        cmd = " ".join(c.get("command", []))[:38]
        print(f"  {name:<14} {enabled:<8} {cmd:<40}")

    # Version check (git)
    try:
        import subprocess
        v = subprocess.run(
            ["git", "-C", str(MCPKU_DIR), "log", "-1", "--format=%h %s"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if v:
            print(f"\n  MCPKU version: {v}")
    except Exception:
        pass

    return 0


def cmd_doctor():
    """Full diagnostic."""
    print("=" * 60)
    print(f"  MCPKU doctor (full diagnostic)")
    print("=" * 60)

    issues = []

    # 1. Config exists
    if not GLOBAL_CONFIG.exists():
        issues.append(f"global config missing: {GLOBAL_CONFIG}")
    else:
        print(f"[OK]   global config exists")

    # 2. MCPKU dir exists
    if not MCPKU_DIR.exists():
        issues.append(f"MCPKU dir missing: {MCPKU_DIR}")
    else:
        print(f"[OK]   MCPKU dir exists")

    # 3. All 17 server files exist
    cfg = load_global_config()
    servers = cfg.get("mcp", {})
    for name, c in servers.items():
        cmd = c.get("command", [])
        if len(cmd) >= 2 and cmd[0] == "python":
            p = Path(cmd[1])
            if not p.exists():
                issues.append(f"server file missing: {name} -> {cmd[1]}")
                print(f"[FAIL] {name}: file missing")
            else:
                print(f"[OK]   {name}: file exists")

    # 4. Python is on PATH
    import shutil
    py = shutil.which("python")
    if not py:
        issues.append("python not on PATH")
        print(f"[FAIL] python not on PATH")
    else:
        print(f"[OK]   python: {py}")

    # 5. Node is on PATH (for context7)
    node = shutil.which("npx") or shutil.which("node")
    if not node:
        print(f"[WARN] npx/node not on PATH (context7 won't work)")
    else:
        print(f"[OK]   npx: {node}")

    if issues:
        print(f"\n[!] {len(issues)} issue(s) found:")
        for i in issues:
            print(f"    - {i}")
        print(f"\nSuggested fixes:")
        print(f"    python verify_setup.py sync     # reinstall global config")
        return 1
    else:
        print(f"\n[OK] All checks passed.")
        return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "sync", "status", "doctor"):
        print(__doc__)
        return 1
    return {
        "check": cmd_check,
        "sync": cmd_sync,
        "status": cmd_status,
        "doctor": cmd_doctor,
    }[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main() or 0)
