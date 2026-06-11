#!/usr/bin/env python3
"""
mcp_wrapper.py — Lightweight auto-diagnostics wrapper for MCPKU servers.

Usage:
    python mcp_wrapper.py <server_filename.py> [args...]

Injects real-time error diagnostics to stderr when errors detected.
Optimized for low overhead under parallel load.
"""

import subprocess
import sys
import json
import os
import threading
import queue
from pathlib import Path

# Add MCPKU to path for imports
MCPKU_ROOT = Path(__file__).parent
sys.path.insert(0, str(MCPKU_ROOT))

from mcp_diagnostics import _classify, _parse_python_traceback


ERROR_KEYWORDS = ("error", "traceback", "exception", "timeout", "failed", "timed out")


def _check_and_inject(line: str) -> None:
    """Check line for error patterns, inject diagnostics if found."""
    lower = line.lower()
    if any(kw in lower for kw in ERROR_KEYWORDS):
        types = _classify(line)
        if types != ["Unknown"]:
            parsed = _parse_python_traceback(line) if "traceback" in lower else {}
            diag = {
                "_mcpku_diagnostics": {
                    "error_types": types,
                    "parsed": parsed,
                    "suggestion": "Error context injected. Run autofix_run with this info."
                }
            }
            print(json.dumps(diag, ensure_ascii=False), file=sys.stderr, flush=True)


def _reader(stream, q: queue.Queue, is_stdout: bool) -> None:
    """Read lines from stream into queue."""
    try:
        for line in stream:
            q.put((line, is_stdout))
    except Exception:
        pass
    finally:
        q.put(None)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python mcp_wrapper.py <server_file.py> [args...]", file=sys.stderr)
        return 1

    server_file = sys.argv[1]
    server_args = sys.argv[2:]

    server_path = MCPKU_ROOT / server_file
    if not server_path.exists():
        print(f"Server not found: {server_path}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(server_path)] + server_args

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )

    q = queue.Queue()
    stdout_thread = threading.Thread(target=_reader, args=(proc.stdout, q, True), daemon=True)
    stderr_thread = threading.Thread(target=_reader, args=(proc.stderr, q, False), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    done_count = 0

    try:
        while done_count < 2:
            try:
                item = q.get(timeout=0.1)
                if item is None:
                    done_count += 1
                    continue
                line, is_stdout = item
                if is_stdout:
                    print(line, end="", flush=True)
                else:
                    print(line, file=sys.stderr, end="", flush=True)
                _check_and_inject(line)
            except queue.Empty:
                pass
    except BrokenPipeError:
        pass
    finally:
        proc.wait()

    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())