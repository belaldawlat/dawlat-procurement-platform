"""In-memory semantic business knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class KnowledgeNode:
    node_id: str
    node_type: str
    label: str


@dataclass(frozen=True)
class KnowledgeEdge:
    source_id: str
    relationship: str
    target_id: str
    confidence_score: int


class KnowledgeGraphEngine:
    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: list[KnowledgeEdge] = []

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.node_id] = node

    def add_edge(self, edge: KnowledgeEdge) -> None:
        if edge.source_id not in self._nodes:
            raise LookupError(
                f"Source node '{edge.source_id}' does not exist."
            )
        if edge.target_id not in self._nodes:
            raise LookupError(
                f"Target node '{edge.target_id}' does not exist."
            )
        self._edges.append(edge)

    def neighbours(
        self,
        node_id: str,
        *,
        relationship: str | None = None,
    ) -> list[KnowledgeNode]:
        target_ids = {
            edge.target_id
            for edge in self._edges
            if edge.source_id == node_id
            and (
                relationship is None
                or edge.relationship == relationship
            )
        }

        return [
            self._nodes[target_id]
            for target_id in target_ids
        ]

    def paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_depth: int = 4,
    ) -> list[list[str]]:
        results: list[list[str]] = []

        def walk(
            current: str,
            path: list[str],
        ) -> None:
            if len(path) > max_depth + 1:
                return
            if current == target_id:
                results.append(path)
                return

            for edge in self._edges:
                if edge.source_id == current:
                    if edge.target_id not in path:
                        walk(
                            edge.target_id,
                            [
                                *path,
                                edge.target_id,
                            ],
                        )

        walk(source_id, [source_id])
        return results


_engine = KnowledgeGraphEngine()


def get_knowledge_graph_engine() -> KnowledgeGraphEngine:
    return _engine