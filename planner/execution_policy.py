"""
execution_policy.py — Per-action execution policies.

Controls retry, timeout, parallel execution, and criticality.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetryStrategy:
    max_retries: int = 2
    backoff_base: float = 1.0
    backoff_multiplier: float = 2.0


@dataclass
class PolicyRule:
    action: str
    max_retries: int = 2
    timeout: int = 60
    critical: bool = True
    parallel_ok: bool = False
    retry_strategy: RetryStrategy = field(default_factory=RetryStrategy)


DEFAULT_POLICIES: dict[str, PolicyRule] = {
    "research": PolicyRule("research", max_retries=2, timeout=30, critical=True, parallel_ok=True),
    "memory": PolicyRule("memory", max_retries=1, timeout=15, critical=False, parallel_ok=False),
    "debug": PolicyRule("debug", max_retries=3, timeout=120, critical=True, parallel_ok=False),
    "git": PolicyRule("git", max_retries=1, timeout=30, critical=False, parallel_ok=False),
    "files": PolicyRule("files", max_retries=1, timeout=30, critical=True, parallel_ok=False),
    "time": PolicyRule("time", max_retries=1, timeout=10, critical=False, parallel_ok=True),
    "plan": PolicyRule("plan", max_retries=1, timeout=20, critical=False, parallel_ok=True),
    "github": PolicyRule("github", max_retries=2, timeout=30, critical=False, parallel_ok=False),
    "db": PolicyRule("db", max_retries=1, timeout=30, critical=False, parallel_ok=False),
}


class ExecutionPolicy:
    def __init__(self, rules: dict[str, PolicyRule] = None):
        self._rules: dict[str, PolicyRule] = {}
        self._rules.update(DEFAULT_POLICIES)
        if rules:
            self._rules.update(rules)

    def get(self, action: str) -> PolicyRule:
        return self._rules.get(action, PolicyRule(action))

    def can_parallel(self, action: str) -> bool:
        return self.get(action).parallel_ok

    def max_retries(self, action: str) -> int:
        return self.get(action).max_retries

    def timeout(self, action: str) -> int:
        return self.get(action).timeout

    def is_critical(self, action: str) -> bool:
        return self.get(action).critical

    def retry_strategy(self, action: str) -> RetryStrategy:
        return self.get(action).retry_strategy
