"""Execution context for enterprise resilience operations."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from app.observability.redaction import redact_mapping


@dataclass(frozen=True)
class ResilienceContext:
    """Immutable context for retry, recovery and circuit operations."""

    operation_name: str
    operation_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    request_id: str = ""
    correlation_id: str = ""
    actor_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    dependency_name: str = ""
    attempt_number: int = 1
    started_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate immutable context values."""

        if not str(self.operation_name or "").strip():
            raise ValueError(
                "Resilience operation name is required."
            )

        if self.attempt_number < 1:
            raise ValueError(
                "Attempt number must be at least 1."
            )

        object.__setattr__(
            self,
            "operation_name",
            str(self.operation_name).strip(),
        )
        object.__setattr__(
            self,
            "operation_id",
            str(self.operation_id or uuid4().hex).strip(),
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
                or self.operation_id
            ).strip(),
        )
        object.__setattr__(
            self,
            "actor_id",
            str(self.actor_id or "").strip(),
        )
        object.__setattr__(
            self,
            "resource_type",
            str(self.resource_type or "").strip(),
        )
        object.__setattr__(
            self,
            "resource_id",
            str(self.resource_id or "").strip(),
        )
        object.__setattr__(
            self,
            "dependency_name",
            str(self.dependency_name or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a redacted structured representation."""

        payload = asdict(self)
        payload["metadata"] = redact_mapping(self.metadata)

        return {
            key: value
            for key, value in payload.items()
            if value not in {"", None}
        }

    def next_attempt(self) -> "ResilienceContext":
        """Return a new context for the next retry attempt."""

        return ResilienceContext(
            operation_name=self.operation_name,
            operation_id=self.operation_id,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            actor_id=self.actor_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            dependency_name=self.dependency_name,
            attempt_number=self.attempt_number + 1,
            started_at=self.started_at,
            metadata=dict(self.metadata),
        )

    def with_metadata(
        self,
        **values: Any,
    ) -> "ResilienceContext":
        """Return a copy with additional redacted metadata."""

        merged = {
            **self.metadata,
            **values,
        }

        return ResilienceContext(
            operation_name=self.operation_name,
            operation_id=self.operation_id,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            actor_id=self.actor_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            dependency_name=self.dependency_name,
            attempt_number=self.attempt_number,
            started_at=self.started_at,
            metadata=merged,
        )


_default_context = ResilienceContext(
    operation_name="unscoped-operation"
)

_current_resilience_context: ContextVar[
    ResilienceContext
] = ContextVar(
    "dawlat_resilience_context",
    default=_default_context,
)


def get_resilience_context() -> ResilienceContext:
    """Return the active resilience context."""

    return _current_resilience_context.get()


def set_resilience_context(
    context: ResilienceContext,
) -> Token[ResilienceContext]:
    """Set the active resilience context."""

    return _current_resilience_context.set(context)


def reset_resilience_context(
    token: Token[ResilienceContext],
) -> None:
    """Restore the previous resilience context."""

    _current_resilience_context.reset(token)


def create_resilience_context(
    operation_name: str,
    *,
    request_id: str = "",
    correlation_id: str = "",
    actor_id: str = "",
    resource_type: str = "",
    resource_id: str = "",
    dependency_name: str = "",
    metadata: dict[str, Any] | None = None,
) -> ResilienceContext:
    """Create a validated resilience context."""

    return ResilienceContext(
        operation_name=operation_name,
        request_id=request_id,
        correlation_id=correlation_id,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        dependency_name=dependency_name,
        metadata=metadata or {},
    )


@contextmanager
def resilience_context(
    context: ResilienceContext,
) -> Iterator[ResilienceContext]:
    """Temporarily activate a resilience context."""

    token = set_resilience_context(context)

    try:
        yield context
    finally:
        reset_resilience_context(token)