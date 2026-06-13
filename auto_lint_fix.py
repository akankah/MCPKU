"""
auto_lint_fix.py — Auto Lint + Fix Wrapper
============================================
Chains pylint → autofix → retry in one pipeline.
Can run standalone (zero LLM) or be called as part of planner/agent workflow.

Usage:
    python auto_lint_fix.py lint --file mcp_encoding.py
    python auto_lint_fix.py lint --project E:/MCPKU --auto-fix
    python auto_lint_fix.py fix --lint-result findings.json
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Direct import from MCP modules (bypass MCP protocol) ────────────────────

# pylint tools (from mcp_pylint)
try:
    from mcp_pylint import lint_file, lint_project, suggest_fixes
except ImportError:
    lint_file = lint_project = suggest_fixes = None

# autofix is async — import the functions directly
try:
    from mcp_autofix import autofix_run as _autofix_run_impl
except ImportError:
    _autofix_run_impl = None


# ── Helpers ──────────────────────────────────────────────────────────────────

_IMPORT_PKG_EXTRACT = re.compile(r"(?:No module named|ImportError)\s*['\"]?([a-zA-Z0-9_.-]+)")

def _extract_package(message: str) -> Optional[str]:
    match = _IMPORT_PKG_EXTRACT.search(message)
    if match:
        return match.group(1)
    return None


# ── Core Logic ───────────────────────────────────────────────────────────────

async def auto_lint(target: str, is_project: bool = False, max_files: int = 100) -> tuple[List[dict], dict]:
    """Run lint and return findings."""
    if lint_file is None or lint_project is None:
        return [], {"error": "mcp_pylint not available. Run: pip install pylint"}

    if is_project:
        result_str = await lint_project(target, max_files=max_files)
    else:
        result_str = await lint_file(target)

    result = json.loads(result_str)
    findings = result.get("findings", [])
    return findings, result


async def auto_fix_imports(findings: List[dict]) -> List[dict]:
    """Auto-fix import errors (E0401) via pip install."""
    fix_results = []
    seen_pkgs = set()

    for f in findings:
        if f.get("message-id") not in ("E0401", "E0602"):
            continue

        pkg = _extract_package(f.get("message", ""))
        if pkg and pkg not in seen_pkgs:
            seen_pkgs.add(pkg)
            cmd = f"pip install {pkg}"
            print(f"  -> Auto-fix: {cmd}")

            if _autofix_run_impl:
                fix_result = await _autofix_run_impl(cmd)
                fix_results.append({
                    "package": pkg,
                    "command": cmd,
                    "result": fix_result,
                })
            else:
                fix_results.append({
                    "package": pkg,
                    "command": cmd,
                    "result": {"error": "mcp_autofix not available"},
                })

    return fix_results


async def auto_lint_fix_pipeline(
    target: str,
    is_project: bool = False,
    max_files: int = 100,
    max_retries: int = 2,
    auto_fix: bool = True,
) -> Dict[str, Any]:
    """Full pipeline: lint → fix → retry → report."""
    print(f"[LINT] Target: {target}")
    pipeline = {
        "target": target,
        "initial_findings_count": 0,
        "fixes_applied": [],
        "retries": [],
        "final_findings_count": 0,
        "still_remaining": [],
    }

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"  [RETRY] Attempt {attempt}/{max_retries}...")

        findings, result = await auto_lint(target, is_project, max_files)

        if attempt == 0:
            pipeline["initial_findings_count"] = len(findings)
            print(f"  [FINDINGS] Total: {len(findings)}")

        if auto_fix and findings:
            # Filter auto-fixable errors (import errors)
            fixable = [f for f in findings if f.get("message-id") in ("E0401", "E0602")]
            if fixable:
                print(f"  [FIX] Auto-fixing {len(fixable)} import errors...")
                fixes = await auto_fix_imports(fixable)
                pipeline["fixes_applied"].extend(fixes)

                # Get suggestions for lint messages
                msg_ids = list(set(f.get("message-id", "") for f in findings if f.get("message-id")))
                try:
                    suggestions_str = await suggest_fixes(msg_ids)
                    suggestions = json.loads(suggestions_str)
                    pipeline["suggestions"] = suggestions.get("suggestions", {})
                except Exception:
                    pass

                pipeline["retries"].append({
                    "attempt": attempt + 1,
                    "findings_before": len(findings),
                    "fixes": fixes,
                })
            else:
                break
        else:
            break

    # Final results
    final_findings, _ = await auto_lint(target, is_project, max_files)
    pipeline["final_findings_count"] = len(final_findings)
    pipeline["still_remaining"] = final_findings

    print(f"  [DONE] {pipeline['initial_findings_count']} -> {pipeline['final_findings_count']} issues")
    return pipeline


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Auto lint + fix pipeline")
    parser.add_argument("target", help="File path or project directory")
    parser.add_argument("--project", action="store_true", help="Lint entire project")
    parser.add_argument("--max-files", type=int, default=100, help="Max files for project scan")
    parser.add_argument("--no-fix", action="store_true", help="Skip auto-fix")
    parser.add_argument("--retries", type=int, default=2, help="Max retries after fix")
    parser.add_argument("--output", type=str, default="", help="Save report to JSON file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    result = asyncio.run(auto_lint_fix_pipeline(
        target=args.target,
        is_project=args.project,
        max_files=args.max_files,
        max_retries=args.retries,
        auto_fix=not args.no_fix,
    ))

    if args.json or args.output:
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"  [SAVED] Report: {args.output}")
        else:
            print(output)
    else:
        # Pretty summary
        print(f"\n{'='*50}")
        print(f"TARGET: {result['target']}")
        print(f"INITIAL FINDINGS: {result['initial_findings_count']}")
        print(f"FIXES APPLIED: {len(result['fixes_applied'])}")
        for f in result['fixes_applied']:
            print(f"  - pip install {f['package']}")
        print(f"FINAL FINDINGS: {result['final_findings_count']}")
        if result['still_remaining']:
            print(f"\nREMAINING ISSUES:")
            for f in result['still_remaining'][:10]:
                print(f"  [{f.get('message-id','')}] {f.get('message','')[:80]}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
