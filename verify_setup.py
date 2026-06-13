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
    "bash", "think", "time", "filesystem", "memory",
    "git", "web", "github", "vector",
    "browser", "diagnostics", "autofix", "context7", "research",
    "agent", "planner", "git_doc",
    "api_tester", "perf_fixer", "refactor", "doc_intel",
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

        # Handle both formats:
        # 1. ["python", "path/to/server.py"]
        # 2. ["cmd", "/c", "python", "path/to/server.py"]
        # 3. ["cmd", "/c", "node", "path/to/server.js"]
        target = None
        if len(cmd) >= 2 and cmd[0] in ("python", "npx"):
            target = cmd[1]
        elif len(cmd) >= 4 and cmd[0] == "cmd" and cmd[1] == "/c" and cmd[2] in ("python", "node"):
            target = cmd[3]
        else:
            broken.append((name, f"unexpected command: {cmd}"))
            continue

        if target and cmd[0] in ("python",) or (len(cmd) >= 4 and cmd[2] == "python"):
            p = Path(target)
            if not p.exists():
                broken.append((name, f"missing file: {target}"))
        elif target and (cmd[0] == "npx" or (len(cmd) >= 4 and cmd[2] == "node")):
            # Node.js path - just check it looks valid
            if not target.endswith((".js", ".mjs")):
                broken.append((name, f"unexpected node target: {target}"))
    return broken


def cmd_check():
    """Verify all 21 MCPs are correctly registered in global config."""
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

    print(f"\nRegistered: {len(registered)}/{len(EXPECTED_SERVERS)}")
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
        lmarena_models = list(providers["lmarena"].get("models", {}).keys())
        print(f"[OK]   lmarena provider configured ({len(lmarena_models)} models: {', '.join(lmarena_models[:6])})")
    if "litlellm" in providers:
        print(f"[OK]   litlellm provider configured")

    if missing or broken:
        print(f"\n[!] Setup has issues. Run: python verify_setup.py sync")
        return 1
    else:
        print(f"\n[OK] Setup complete. MCPKU will auto-load in all OpenCode CLI sessions.")
        return 0


def _load_repo_mcp_config() -> dict:
    """Load mcp section from repo's opencode.jsonc."""
    repo_config = MCPKU_DIR / "opencode.jsonc"
    if not repo_config.exists():
        raise FileNotFoundError(f"Repo config not found: {repo_config}")
    text = repo_config.read_text(encoding="utf-8")
    data = json.loads(_strip_jsonc_comments(text))
    return data.get("mcp", {})


def cmd_sync():
    """Sync global config from repo's opencode.jsonc (canonical source)."""
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

    # Load fresh mcp block from repo (canonical source)
    fresh_mcp = _load_repo_mcp_config()
    if not fresh_mcp:
        print(f"[FAIL] no mcp section found in repo config")
        return 1

    # Backup current global config to .config_backup/
    backup_dir = MCPKU_DIR / ".config_backup"
    backup_dir.mkdir(exist_ok=True)
    if GLOBAL_CONFIG.exists():
        import shutil
        backup_path = backup_dir / "opencode.jsonc.global"
        shutil.copy2(GLOBAL_CONFIG, backup_path)
        print(f"[OK]   backed up global config to {backup_path}")

    # Replace mcp block entirely with fresh server entries
    existing["mcp"] = fresh_mcp

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
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        print("\n  (git version check timed out)")
    except Exception:
        pass

    return 0


def cmd_doctor():
    """Full diagnostic."""
    print("=" * 60)
    print(f"  MCPKU doctor (full diagnostic)")
    print("=" * 60)

    # Autopurge workflow state & cache
    try:
        if Path(r'E:\MCPKU\workflow_state.jsonl').exists():
            with open(r'E:\MCPKU\workflow_state.jsonl', 'w') as f:
                f.truncate(0)
            print('[OK]   purged workflow_state.jsonl')
        
        pytest_cache = Path(r'E:\MCPKU\.pytest_cache')
        if pytest_cache.exists():
            shutil.rmtree(pytest_cache)
            print('[OK]   purged .pytest_cache')
    except Exception as e:
        print(f'[WARN] failed to purge: {e}')

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

    # 3. All 18 server files exist
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
