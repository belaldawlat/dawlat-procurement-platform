"""Deterministic relationship traversal for enterprise knowledge."""

from __future__ import annotations

from collections import deque

from app.orchestration.enterprise_knowledge_models import (
    KnowledgeRelationship,
)
from app.orchestration.enterprise_knowledge_result import KnowledgePath


class EnterpriseRelationshipGraph:
    def find_paths(
        self,
        *,
        start_entity_id: str,
        target_entity_id: str,
        relationships: tuple[KnowledgeRelationship, ...],
        maximum_depth: int,
        minimum_weight: float = 0.0,
    ) -> tuple[KnowledgePath, ...]:
        if maximum_depth < 1:
            raise ValueError("Maximum depth must be at least 1.")

        adjacency: dict[
            str,
            list[tuple[str, KnowledgeRelationship]],
        ] = {}

        for relationship in relationships:
            if relationship.weight < minimum_weight:
                continue
            adjacency.setdefault(
                relationship.source_entity_id,
                [],
            ).append(
                (
                    relationship.target_entity_id,
                    relationship,
                )
            )

        queue = deque(
            [
                (
                    start_entity_id,
                    (start_entity_id,),
                    (),
                    1.0,
                )
            ]
        )
        paths: list[KnowledgePath] = []

        while queue:
            current, entity_path, relationship_path, total_weight = (
                queue.popleft()
            )

            if len(relationship_path) >= maximum_depth:
                continue

            for next_entity, relationship in sorted(
                adjacency.get(current, []),
                key=lambda item: (
                    item[0],
                    item[1].relationship_id,
                ),
            ):
                if next_entity in entity_path:
                    continue

                next_entities = entity_path + (next_entity,)
                next_relationships = (
                    relationship_path
                    + (relationship.relationship_id,)
                )
                next_weight = round(
                    total_weight * relationship.weight,
                    6,
                )

                if next_entity == target_entity_id:
                    paths.append(
                        KnowledgePath(
                            entity_ids=next_entities,
                            relationship_ids=next_relationships,
                            total_weight=next_weight,
                        )
                    )
                    continue

                queue.append(
                    (
                        next_entity,
                        next_entities,
                        next_relationships,
                        next_weight,
                    )
                )

        return tuple(
            sorted(
                paths,
                key=lambda path: (
                    len(path.relationship_ids),
                    -path.total_weight,
                    path.entity_ids,
                ),
            )
        )