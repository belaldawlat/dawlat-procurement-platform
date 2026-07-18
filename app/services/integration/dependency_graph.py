"""Dependency graph for platform services and engines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyNode:
    name: str
    node_type: str


class DependencyGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, DependencyNode] = {}
        self._dependencies: dict[str, set[str]] = {}

    def add_node(self, node: DependencyNode) -> None:
        self._nodes[node.name] = node
        self._dependencies.setdefault(node.name, set())

    def add_dependency(
        self,
        *,
        node_name: str,
        depends_on: str,
    ) -> None:
        if node_name not in self._nodes:
            raise LookupError(f"Node '{node_name}' does not exist.")
        if depends_on not in self._nodes:
            raise LookupError(f"Dependency '{depends_on}' does not exist.")
        self._dependencies[node_name].add(depends_on)
        self._assert_acyclic()

    def dependencies_for(self, node_name: str) -> tuple[str, ...]:
        if node_name not in self._nodes:
            raise LookupError(f"Node '{node_name}' does not exist.")
        return tuple(sorted(self._dependencies.get(node_name, set())))

    def execution_order(self) -> tuple[str, ...]:
        visited: set[str] = set()
        visiting: set[str] = set()
        order: list[str] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise ValueError("Dependency cycle detected.")

            visiting.add(node)

            for dependency in self._dependencies.get(node, set()):
                visit(dependency)

            visiting.remove(node)
            visited.add(node)
            order.append(node)

        for node in self._nodes:
            visit(node)

        return tuple(order)

    def _assert_acyclic(self) -> None:
        self.execution_order()


_graph = DependencyGraph()


def get_dependency_graph() -> DependencyGraph:
    return _graph