"""Audit pipeline for platform operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.integration.execution_context import ExecutionContext


@dataclass(frozen=True)
class AuditRecord:
    action_name: str
    result: str
    actor_id: str
    actor_role: str
    correlation_id: str
    context_id: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class AuditPipeline:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(
        self,
        *,
        action_name: str,
        result: str,
        context: ExecutionContext,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        record = AuditRecord(
            action_name=action_name,
            result=result,
            actor_id=context.actor_id,
            actor_role=context.actor_role,
            correlation_id=context.correlation_id,
            context_id=context.context_id,
            details=details or {},
        )
        self._records.append(record)
        return record

    def list_for_correlation(
        self,
        correlation_id: str,
    ) -> tuple[AuditRecord, ...]:
        return tuple(
            record
            for record in self._records
            if record.correlation_id == correlation_id
        )


_pipeline = AuditPipeline()


def get_audit_pipeline() -> AuditPipeline:
    return _pipeline