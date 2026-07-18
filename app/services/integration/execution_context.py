"""Execution context for enterprise platform orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ExecutionContext:
    context_id: str
    correlation_id: str
    actor_id: str
    actor_role: str
    case_id: str | None = None
    workflow_id: str | None = None
    source: str = "Platform"
    approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @classmethod
    def create(
        cls,
        *,
        actor_id: str,
        actor_role: str,
        case_id: str | None = None,
        workflow_id: str | None = None,
        source: str = "Platform",
        approved: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionContext":
        return cls(
            context_id=f"CTX-{uuid4().hex[:16].upper()}",
            correlation_id=f"COR-{uuid4().hex[:16].upper()}",
            actor_id=actor_id,
            actor_role=actor_role,
            case_id=case_id,
            workflow_id=workflow_id,
            source=source,
            approved=approved,
            metadata=metadata or {},
        )