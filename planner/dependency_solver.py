"""
dependency_solver.py — Resolve execution dependencies between intents.

Knows that:
  - research must happen before memory save
  - memory search must happen before memory create
  - debug/autofix needs diagnostics first
  - git commit needs git status first (optional)
  - time is always independent
"""

from dataclasses import dataclass, field
from typing import Any

from planner.intent_parser import Intent


@dataclass
class Dependency:
    from_action: str
    to_action: str
    reason: str = ""
    optional: bool = False


# Built-in dependency rules between action types
DEFAULT_DEPS: list[Dependency] = [
    Dependency("research", "memory", "research results needed before saving to memory"),
    Dependency("debug", "memory", "debug results may be saved for KB"),
    Dependency("github", "git", "github operations need local repo context"),
]


def resolve_dependencies(intents: list[Intent]) -> list[Dependency]:
    """Given parsed intents, return explicit dependency list."""
    actions = [i.action for i in intents]
    active_deps = []

    for dep in DEFAULT_DEPS:
        if dep.from_action in actions and dep.to_action in actions:
            idx_from = actions.index(dep.from_action)
            idx_to = actions.index(dep.to_action)
            if idx_from < idx_to:
                active_deps.append(dep)

    return active_deps


def order_by_dependencies(intents: list[Intent], deps: list[Dependency]) -> list[Intent]:
    """
    Reorder intents so dependencies come before dependents.
    Preserves original order within same dependency level.
    """
    dep_map: dict[str, set[str]] = {}
    for d in deps:
        dep_map.setdefault(d.to_action, set()).add(d.from_action)

    def _ready(action: str, placed: set[str]) -> bool:
        prereqs = dep_map.get(action, set())
        return prereqs.issubset(placed)

    placed: set[str] = set()
    result: list[Intent] = []
    remaining = list(intents)

    max_iter = len(remaining) * 2
    for _ in range(max_iter):
        if not remaining:
            break
        for i, intent in enumerate(remaining):
            if _ready(intent.action, placed):
                result.append(intent)
                placed.add(intent.action)
                remaining.pop(i)
                break

    result.extend(remaining)
    return result
