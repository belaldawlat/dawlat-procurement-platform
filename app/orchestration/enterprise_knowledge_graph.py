"""Enterprise knowledge graph service."""

from __future__ import annotations

from app.orchestration.enterprise_graph_store import EnterpriseGraphStore
from app.orchestration.enterprise_knowledge_models import (
    KnowledgeEntity,
    KnowledgeRelationship,
)
from app.orchestration.enterprise_knowledge_policy import (
    EnterpriseKnowledgePolicy,
)
from app.orchestration.enterprise_knowledge_result import (
    EnterpriseKnowledgeResult,
)
from app.orchestration.enterprise_relationship_graph import (
    EnterpriseRelationshipGraph,
)
from app.orchestration.exceptions import WorkflowIntegrityError


class EnterpriseKnowledgeGraph:
    def __init__(
        self,
        *,
        policy: EnterpriseKnowledgePolicy | None = None,
        store: EnterpriseGraphStore | None = None,
        relationship_graph: EnterpriseRelationshipGraph | None = None,
    ) -> None:
        self._policy = policy or EnterpriseKnowledgePolicy(
            policy_id="default-enterprise-knowledge",
            name="Default Enterprise Knowledge Policy",
        )
        self._store = store or EnterpriseGraphStore()
        self._relationship_graph = (
            relationship_graph or EnterpriseRelationshipGraph()
        )

    @property
    def policy(self) -> EnterpriseKnowledgePolicy:
        return self._policy

    @property
    def store(self) -> EnterpriseGraphStore:
        return self._store

    def add_entity(
        self,
        entity: KnowledgeEntity,
    ) -> KnowledgeEntity:
        if not self._policy.enabled:
            raise ValueError(
                "Enterprise knowledge policy is disabled."
            )

        if self._policy.reject_duplicate_external_ids:
            return self._store.add_entity(entity)

        try:
            existing = self._store.get_entity_by_external_id(
                entity.external_id
            )
            return existing
        except Exception:
            return self._store.add_entity(entity)

    def add_relationship(
        self,
        relationship: KnowledgeRelationship,
    ) -> KnowledgeRelationship:
        if not self._policy.enabled:
            raise ValueError(
                "Enterprise knowledge policy is disabled."
            )

        if (
            self._policy.require_existing_entities_for_relationships
        ):
            try:
                self._store.get_entity(
                    relationship.source_entity_id
                )
                self._store.get_entity(
                    relationship.target_entity_id
                )
            except Exception as exc:
                raise WorkflowIntegrityError(
                    technical_message=(
                        "Relationship endpoints must exist before "
                        "the relationship is created."
                    )
                ) from exc

        if not self._policy.allow_cycle_creation:
            reverse_paths = self._relationship_graph.find_paths(
                start_entity_id=relationship.target_entity_id,
                target_entity_id=relationship.source_entity_id,
                relationships=self._store.list_relationships(),
                maximum_depth=self._policy.maximum_traversal_depth,
                minimum_weight=(
                    self._policy.minimum_relationship_weight
                ),
            )
            if reverse_paths:
                raise WorkflowIntegrityError(
                    technical_message=(
                        "Relationship would create a graph cycle."
                    )
                )

        return self._store.add_relationship(relationship)

    def query_entity(
        self,
        entity_id: str,
    ) -> EnterpriseKnowledgeResult:
        entity = self._store.get_entity(entity_id)
        relationships = tuple(
            relationship
            for relationship in self._store.list_relationships()
            if entity.entity_id
            in {
                relationship.source_entity_id,
                relationship.target_entity_id,
            }
        )

        related_ids = {
            entity.entity_id
        } | {
            relationship.source_entity_id
            for relationship in relationships
        } | {
            relationship.target_entity_id
            for relationship in relationships
        }

        entities = tuple(
            item
            for item in self._store.list_entities()
            if item.entity_id in related_ids
        )

        return EnterpriseKnowledgeResult(
            entities=entities,
            relationships=relationships,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={"query_entity_id": entity_id},
        )

    def find_paths(
        self,
        start_entity_id: str,
        target_entity_id: str,
        *,
        maximum_depth: int | None = None,
    ) -> EnterpriseKnowledgeResult:
        self._store.get_entity(start_entity_id)
        self._store.get_entity(target_entity_id)

        depth = (
            maximum_depth
            if maximum_depth is not None
            else self._policy.maximum_traversal_depth
        )

        if depth > self._policy.maximum_traversal_depth:
            raise ValueError(
                "Requested traversal depth exceeds policy."
            )

        paths = self._relationship_graph.find_paths(
            start_entity_id=start_entity_id,
            target_entity_id=target_entity_id,
            relationships=self._store.list_relationships(),
            maximum_depth=depth,
            minimum_weight=self._policy.minimum_relationship_weight,
        )[: self._policy.maximum_results]

        entity_ids = {
            entity_id
            for path in paths
            for entity_id in path.entity_ids
        }
        relationship_ids = {
            relationship_id
            for path in paths
            for relationship_id in path.relationship_ids
        }

        entities = tuple(
            entity
            for entity in self._store.list_entities()
            if entity.entity_id in entity_ids
        )
        relationships = tuple(
            relationship
            for relationship in self._store.list_relationships()
            if relationship.relationship_id in relationship_ids
        )

        return EnterpriseKnowledgeResult(
            entities=entities,
            relationships=relationships,
            paths=paths,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "start_entity_id": start_entity_id,
                "target_entity_id": target_entity_id,
                "maximum_depth": depth,
            },
        )

    def impact_analysis(
        self,
        entity_id: str,
        *,
        maximum_depth: int | None = None,
    ) -> EnterpriseKnowledgeResult:
        self._store.get_entity(entity_id)
        depth = (
            maximum_depth
            if maximum_depth is not None
            else self._policy.maximum_traversal_depth
        )

        relationships = self._store.list_relationships()
        impacted_ids = {entity_id}
        frontier = {entity_id}

        for _ in range(depth):
            next_frontier: set[str] = set()

            for relationship in relationships:
                if relationship.weight < (
                    self._policy.minimum_relationship_weight
                ):
                    continue

                if relationship.source_entity_id in frontier:
                    next_frontier.add(
                        relationship.target_entity_id
                    )

            next_frontier -= impacted_ids

            if not next_frontier:
                break

            impacted_ids.update(next_frontier)
            frontier = next_frontier

        impacted_relationships = tuple(
            relationship
            for relationship in relationships
            if (
                relationship.source_entity_id in impacted_ids
                and relationship.target_entity_id in impacted_ids
            )
        )
        impacted_entities = tuple(
            entity
            for entity in self._store.list_entities()
            if entity.entity_id in impacted_ids
        )

        return EnterpriseKnowledgeResult(
            entities=impacted_entities,
            relationships=impacted_relationships,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "root_entity_id": entity_id,
                "impact_depth": depth,
            },
        )


_default_enterprise_knowledge_graph = EnterpriseKnowledgeGraph()


def get_enterprise_knowledge_graph() -> EnterpriseKnowledgeGraph:
    return _default_enterprise_knowledge_graph