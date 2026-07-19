"""Results produced by the enterprise knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_knowledge_models import (
    KnowledgeEntity,
    KnowledgeRelationship,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class KnowledgePath:
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    total_weight: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_ids": list(self.entity_ids),
            "relationship_ids": list(self.relationship_ids),
            "total_weight": self.total_weight,
        }


@dataclass(frozen=True)
class EnterpriseKnowledgeResult:
    entities: tuple[KnowledgeEntity, ...]
    relationships: tuple[KnowledgeRelationship, ...]
    paths: tuple[KnowledgePath, ...] = ()
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "relationships", tuple(self.relationships))
        object.__setattr__(self, "paths", tuple(self.paths))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(
            self,
            "policy_version",
            str(self.policy_version or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
            "path_count": len(self.paths),
            "entities": [entity.as_dict() for entity in self.entities],
            "relationships": [
                relationship.as_dict()
                for relationship in self.relationships
            ],
            "paths": [path.as_dict() for path in self.paths],
            "metadata": redact_mapping(self.metadata),
        }