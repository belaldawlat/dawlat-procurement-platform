"""Workflow template models for enterprise workflow intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowPriority,
    EnterpriseWorkflowStage,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseWorkflowTemplate:
    """Immutable reusable enterprise workflow template."""

    name: str
    stages: tuple[EnterpriseWorkflowStage, ...]
    template_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    version: str = "1.0.0"
    description: str = ""
    category: str = "general"
    active: bool = True
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.template_id or "").strip():
            raise ValueError("Workflow template ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Workflow template name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Workflow template version is required.")
        if not self.stages:
            raise ValueError(
                "Workflow template requires at least one stage."
            )

        stage_ids = [stage.stage_id for stage in self.stages]

        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError(
                "Workflow template stage IDs must be unique."
            )

        object.__setattr__(
            self,
            "template_id",
            str(self.template_id).strip(),
        )
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(
            self,
            "category",
            str(self.category or "general").strip(),
        )
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def instantiate(
        self,
        *,
        case_id: str,
        workflow_name: str | None = None,
        correlation_id: str = "",
        priority: EnterpriseWorkflowPriority = (
            EnterpriseWorkflowPriority.NORMAL
        ),
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseWorkflow:
        """Create a new workflow instance from this template."""

        if not self.active:
            raise ValueError(
                "Inactive workflow templates cannot be instantiated."
            )

        stages = tuple(
            replace(
                stage,
                tasks=tuple(replace(task) for task in stage.tasks),
            )
            for stage in self.stages
        )

        combined_metadata = {
            **redact_mapping(self.metadata),
            **redact_mapping(metadata or {}),
        }

        return EnterpriseWorkflow(
            case_id=case_id,
            name=workflow_name or self.name,
            stages=stages,
            template_id=self.template_id,
            template_version=self.version,
            priority=priority,
            correlation_id=correlation_id,
            metadata=combined_metadata,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "template_id": self.template_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "active": self.active,
            "created_at": self.created_at,
            "stages": [stage.as_dict() for stage in self.stages],
            "metadata": redact_mapping(self.metadata),
        }