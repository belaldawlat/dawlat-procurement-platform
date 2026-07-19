"""Policy configuration for the enterprise knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseKnowledgePolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_traversal_depth: int = 5
    maximum_results: int = 500
    minimum_relationship_weight: float = 0.0
    reject_duplicate_external_ids: bool = True
    require_existing_entities_for_relationships: bool = True
    allow_cycle_creation: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Knowledge policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Knowledge policy name is required.")
        if self.maximum_traversal_depth < 1:
            raise ValueError("Maximum traversal depth must be at least 1.")
        if self.maximum_results < 1:
            raise ValueError("Maximum results must be at least 1.")
        if not 0 <= self.minimum_relationship_weight <= 1:
            raise ValueError(
                "Minimum relationship weight must be between 0 and 1."
            )

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version or "1.0.0").strip())