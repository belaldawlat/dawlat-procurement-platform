"""Request and actor context for structured enterprise logging."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from typing import Iterator
from uuid import uuid4


@dataclass(frozen=True)
class LogContext:
    """Immutable contextual metadata attached to log records."""

    request_id: str = ""
    correlation_id: str = ""
    actor_id: str = ""
    actor_email: str = ""
    actor_role: str = ""
    session_id: str = ""
    source_ip: str = ""
    user_agent: str = ""

    def as_dict(self) -> dict[str, str]:
        """Return populated context fields as a dictionary."""

        return {
            key: value
            for key, value in asdict(self).items()
            if value
        }


_current_context: ContextVar[LogContext] = ContextVar(
    "dawlat_log_context",
    default=LogContext(),
)


def get_log_context() -> LogContext:
    """Return the active logging context."""

    return _current_context.get()


def set_log_context(context: LogContext) -> Token[LogContext]:
    """Set the active logging context and return its reset token."""

    return _current_context.set(context)


def reset_log_context(token: Token[LogContext]) -> None:
    """Restore the previous logging context."""

    _current_context.reset(token)


def create_request_context(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str = "",
    actor_email: str = "",
    actor_role: str = "",
    session_id: str = "",
    source_ip: str = "",
    user_agent: str = "",
) -> LogContext:
    """Create a normalised request context."""

    resolved_request_id = (
        str(request_id).strip()
        if request_id
        else uuid4().hex
    )

    resolved_correlation_id = (
        str(correlation_id).strip()
        if correlation_id
        else resolved_request_id
    )

    return LogContext(
        request_id=resolved_request_id,
        correlation_id=resolved_correlation_id,
        actor_id=str(actor_id or "").strip(),
        actor_email=str(actor_email or "").strip(),
        actor_role=str(actor_role or "").strip(),
        session_id=str(session_id or "").strip(),
        source_ip=str(source_ip or "").strip(),
        user_agent=str(user_agent or "").strip(),
    )


@contextmanager
def logging_context(
    context: LogContext,
) -> Iterator[LogContext]:
    """Temporarily activate a logging context."""

    token = set_log_context(context)

    try:
        yield context
    finally:
        reset_log_context(token)