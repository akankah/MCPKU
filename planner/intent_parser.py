"""
intent_parser.py — Parse user goal into structured intents.

Each intent represents a discrete action in the plan:
  Intent(action="research", target="bitcoin price", params={...})
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    action: str
    target: str = ""
    params: dict = field(default_factory=dict)
    confidence: float = 1.0


INTENT_RULES = [
    # (keywords, action, param_overrides)
    (["research", "cari", "cek", "trend", "info", "berita", "analisa", "analisis"], "research", {}),
    (["memory", "simpan", "ingat", "catat", "save", "recall"], "memory", {}),
    (["debug", "fix", "error", "bug", "gagal", "perbaiki"], "debug", {}),
    (["file", "baca", "tulis", "read", "write", "buat", "hapus"], "files", {}),
    (["git", "commit", "push", "pull", "status", "log", "branch"], "git", {}),
    (["waktu", "time", "jam", "tanggal", "date"], "time", {}),
    (["workflow", "automasi", "pipeline", "plan", "otomatis"], "plan", {}),
    (["github", "pr", "issue", "repo", "gh"], "github", {}),
    (["sql", "database", "db", "query"], "db", {}),
]


def parse_goal(goal: str, context: str = "") -> list[Intent]:
    """Parse a natural-language goal into structured intents."""
    goal_lower = goal.lower()
    intents: list[Intent] = []
    seen = set()

    for keywords, action, param_overrides in INTENT_RULES:
        if any(kw in goal_lower for kw in keywords):
            if action not in seen:
                seen.add(action)
                intent = Intent(
                    action=action,
                    target=goal[:60],
                    params={"query": goal, "context": context, **param_overrides},
                )
                intents.append(intent)

    if not intents:
        intents.append(Intent(
            action="research",
            target=goal[:60],
            params={"query": goal, "context": context},
            confidence=0.5,
        ))
        intents.append(Intent(
            action="memory",
            target=goal[:60],
            params={"query": goal, "context": context},
            confidence=0.5,
        ))

    return intents
