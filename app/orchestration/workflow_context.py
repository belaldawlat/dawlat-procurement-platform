"""Immutable execution context for enterprise workflows."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from app.observability.redaction import redact_mapping


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkflowContext:
    """Security-conscious context shared across workflow operations."""

    workflow_id: str
    workflow_version: str
    instance_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    correlation_id: str = ""
    request_id: str = ""
    actor_id: str = ""
    actor_role: str = ""
    tenant_id: str = ""
    business_unit: str = ""
    country_code: str = ""
    current_step_id: str = ""
    attempt_number: int = 1
    started_at: str = field(default_factory=_utc_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalise immutable context data."""

        workflow_id = str(self.workflow_id or "").strip()
        workflow_version = str(
            self.workflow_version or ""
        ).strip()
        instance_id = str(
            self.instance_id or uuid4().hex
        ).strip()

        if not workflow_id:
            raise ValueError("Workflow ID is required.")

        if not workflow_version:
            raise ValueError("Workflow version is required.")

        if self.attempt_number < 1:
            raise ValueError(
                "Attempt number must be at least 1."
            )

        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(
            self,
            "workflow_version",
            workflow_version,
        )
        object.__setattr__(
            self,
            "instance_id",
            instance_id,
        )
        object.__setattr__(
            self,
            "request_id",
            str(self.request_id or "").strip(),
        )
        object.__setattr__(
            self,
            "correlation_id",
            str(
                self.correlation_id
                or self.request_id
                or instance_id
            ).strip(),
        )
        object.__setattr__(
            self,
            "actor_id",
            str(self.actor_id or "").strip(),
        )
        object.__setattr__(
            self,
            "actor_role",
            str(self.actor_role or "").strip(),
        )
        object.__setattr__(
            self,
            "tenant_id",
            str(self.tenant_id or "").strip(),
        )
        object.__setattr__(
            self,
            "business_unit",
            str(self.business_unit or "").strip(),
        )
        object.__setattr__(
            self,
            "country_code",
            str(self.country_code or "").strip().upper(),
        )
        object.__setattr__(
            self,
            "current_step_id",
            str(self.current_step_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a redacted serialisable context."""

        payload = asdict(self)
        payload["metadata"] = redact_mapping(self.metadata)

        return {
            key: value
            for key, value in payload.items()
            if value not in {"", None}
        }

    def for_step(
        self,
        step_id: str,
    ) -> "WorkflowContext":
        """Return a context focused on a workflow step."""

        cleaned_step_id = str(step_id or "").strip()

        if not cleaned_step_id:
            raise ValueError("Workflow step ID is required.")

        return replace(
            self,
            current_step_id=cleaned_step_id,
        )

    def next_attempt(self) -> "WorkflowContext":
        """Return a context for the next execution attempt."""

        return replace(
            self,
            attempt_number=self.attempt_number + 1,
        )

    def with_metadata(
        self,
        **values: Any,
    ) -> "WorkflowContext":
        """Return a copy containing additional redacted metadata."""

        return replace(
            self,
            metadata=redact_mapping(
                {
                    **self.metadata,
                    **values,
                }
            ),
        )


_default_context = WorkflowContext(
    workflow_id="unscoped-workflow",
    workflow_version="0",
)

_current_workflow_context: ContextVar[
    WorkflowContext
] = ContextVar(
    "dawlat_workflow_context",
    default=_default_context,
)


def get_workflow_context() -> WorkflowContext:
    """Return the active workflow context."""

    return _current_workflow_context.get()


def set_workflow_context(
    context: WorkflowContext,
) -> Token[WorkflowContext]:
    """Set the active workflow context."""

    return _current_workflow_context.set(context)


def reset_workflow_context(
    token: Token[WorkflowContext],
) -> None:
    """Restore the previous workflow context."""

    _current_workflow_context.reset(token)


def create_workflow_context(
    workflow_id: str,
    workflow_version: str,
    *,
    request_id: str = "",
    correlation_id: str = "",
    actor_id: str = "",
    actor_role: str = "",
    tenant_id: str = "",
    business_unit: str = "",
    country_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> WorkflowContext:
    """Create a validated workflow context."""

    return WorkflowContext(
        workflow_id=workflow_id,
        workflow_version=workflow_version,
        request_id=request_id,
        correlation_id=correlation_id,
        actor_id=actor_id,
        actor_role=actor_role,
        tenant_id=tenant_id,
        business_unit=business_unit,
        country_code=country_code,
        metadata=metadata or {},
    )


@contextmanager
def workflow_context(
    context: WorkflowContext,
) -> Iterator[WorkflowContext]:
    """Temporarily activate a workflow context."""

    token = set_workflow_context(context)

    try:
        yield context
    finally:
        reset_workflow_context(token)