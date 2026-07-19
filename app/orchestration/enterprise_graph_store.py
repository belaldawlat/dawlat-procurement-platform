"""Thread-safe persistence for enterprise knowledge entities and relationships."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_knowledge_models import (
    KnowledgeEntity,
    KnowledgeRelationship,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


class EnterpriseGraphStore:
    def __init__(self) -> None:
        self._entities: dict[str, KnowledgeEntity] = {}
        self._external_index: dict[str, str] = {}
        self._relationships: dict[str, KnowledgeRelationship] = {}
        self._lock = threading.RLock()

    def add_entity(self, entity: KnowledgeEntity) -> KnowledgeEntity:
        if not isinstance(entity, KnowledgeEntity):
            raise TypeError("Graph store requires a KnowledgeEntity.")

        with self._lock:
            if entity.entity_id in self._entities:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Knowledge entity {entity.entity_id!r} already exists."
                    )
                )
            if entity.external_id in self._external_index:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Knowledge external ID {entity.external_id!r} "
                        "already exists."
                    )
                )

            self._entities[entity.entity_id] = entity
            self._external_index[entity.external_id] = entity.entity_id

        return entity

    def get_entity(self, entity_id: str) -> KnowledgeEntity:
        cleaned = str(entity_id or "").strip()
        if not cleaned:
            raise ValueError("Knowledge entity ID is required.")

        with self._lock:
            entity = self._entities.get(cleaned)

        if entity is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Knowledge entity {cleaned!r} was not found."
                )
            )

        return entity

    def get_entity_by_external_id(
        self,
        external_id: str,
    ) -> KnowledgeEntity:
        cleaned = str(external_id or "").strip()
        if not cleaned:
            raise ValueError("Knowledge external ID is required.")

        with self._lock:
            entity_id = self._external_index.get(cleaned)

        if entity_id is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Knowledge external ID {cleaned!r} was not found."
                )
            )

        return self.get_entity(entity_id)

    def add_relationship(
        self,
        relationship: KnowledgeRelationship,
    ) -> KnowledgeRelationship:
        if not isinstance(relationship, KnowledgeRelationship):
            raise TypeError(
                "Graph store requires a KnowledgeRelationship."
            )

        with self._lock:
            if relationship.relationship_id in self._relationships:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Knowledge relationship "
                        f"{relationship.relationship_id!r} already exists."
                    )
                )
            self._relationships[relationship.relationship_id] = relationship

        return relationship

    def get_relationship(
        self,
        relationship_id: str,
    ) -> KnowledgeRelationship:
        cleaned = str(relationship_id or "").strip()
        if not cleaned:
            raise ValueError("Knowledge relationship ID is required.")

        with self._lock:
            relationship = self._relationships.get(cleaned)

        if relationship is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Knowledge relationship {cleaned!r} was not found."
                )
            )

        return relationship

    def list_entities(self) -> tuple[KnowledgeEntity, ...]:
        with self._lock:
            return tuple(
                self._entities[key]
                for key in sorted(self._entities)
            )

    def list_relationships(
        self,
    ) -> tuple[KnowledgeRelationship, ...]:
        with self._lock:
            return tuple(
                self._relationships[key]
                for key in sorted(self._relationships)
            )

    def clear(self) -> None:
        with self._lock:
            self._entities.clear()
            self._external_index.clear()
            self._relationships.clear()


_default_enterprise_graph_store = EnterpriseGraphStore()


def get_enterprise_graph_store() -> EnterpriseGraphStore:
    return _default_enterprise_graph_store