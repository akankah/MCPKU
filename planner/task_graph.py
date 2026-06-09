"""
task_graph.py — DAG-based execution graph for plan steps.

Supports dependency tracking, topological sort, parallel groups,
and cycle detection.
"""

from typing import Any


class TaskGraph:
    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, list[str]] = {}  # node_id -> list of dependency_ids

    def add_node(self, node_id: str, data: dict = None):
        if node_id not in self._nodes:
            self._nodes[node_id] = data or {}
            self._edges[node_id] = []

    def add_dependency(self, node_id: str, depends_on: str):
        if node_id not in self._nodes:
            self.add_node(node_id)
        if depends_on not in self._nodes:
            self.add_node(depends_on)
        if depends_on not in self._edges[node_id]:
            self._edges[node_id].append(depends_on)

    def get_dependencies(self, node_id: str) -> list[str]:
        return self._edges.get(node_id, [])

    def get_dependents(self, node_id: str) -> list[str]:
        return [nid for nid, deps in self._edges.items() if node_id in deps]

    def has_cycle(self) -> bool:
        visited = set()
        rec_stack = set()

        def _dfs(nid):
            visited.add(nid)
            rec_stack.add(nid)
            for dep in self._edges.get(nid, []):
                if dep not in visited:
                    if _dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(nid)
            return False

        for nid in self._nodes:
            if nid not in visited:
                if _dfs(nid):
                    return True
        return False

    def topological_sort(self) -> list[str]:
        """Return node IDs in execution order (dependencies first)."""
        if self.has_cycle():
            raise ValueError("TaskGraph has a cycle; cannot topological sort")

        visited = set()
        result = []

        def _dfs(nid):
            if nid in visited:
                return
            visited.add(nid)
            for dep in self._edges.get(nid, []):
                _dfs(dep)
            result.append(nid)

        for nid in self._nodes:
            _dfs(nid)
        return result

    def get_parallel_groups(self) -> list[list[str]]:
        """
        Group nodes that can execute in parallel.
        Each group has no inter-dependencies.
        """
        order = self.topological_sort()
        depths: dict[str, int] = {}

        for nid in order:
            deps = self._edges.get(nid, [])
            if not deps:
                depths[nid] = 0
            else:
                depths[nid] = max(depths.get(d, -1) for d in deps) + 1

        groups: dict[int, list[str]] = {}
        for nid, depth in depths.items():
            groups.setdefault(depth, []).append(nid)

        max_depth = max(groups.keys()) if groups else -1
        return [groups.get(d, []) for d in range(max_depth + 1)]

    def node_count(self) -> int:
        return len(self._nodes)

    def get_all_nodes(self) -> dict[str, dict]:
        return dict(self._nodes)
