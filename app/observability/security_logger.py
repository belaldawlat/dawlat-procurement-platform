"""Security-focused event logging."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.audit_logger import (
    AuditEvent,
    AuditOutcome,
    get_audit_logger,
)
from app.observability.logging_config import get_logger
from app.observability.redaction import redact_mapping


class SecuritySeverity(str, Enum):
    """Security event severity levels."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SecurityEvent:
    """Immutable security event."""

    event_type: str
    severity: SecuritySeverity
    message: str

    actor_id: str = ""
    actor_email: str = ""
    source_ip: str = ""
    request_id: str = ""
    session_id: str = ""

    details: dict[str, Any] = field(default_factory=dict)

    event_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    occurred_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class SecurityLogger:
    """Record security events in application and audit logs."""

    def __init__(self) -> None:
        self._logger = get_logger("security")
        self._audit_logger = get_audit_logger()

    def record(self, event: SecurityEvent) -> None:
        """Record a security event."""

        payload = asdict(event)
        payload["severity"] = event.severity.value
        payload["details"] = redact_mapping(event.details)

        log_level = self._resolve_log_level(event.severity)

        self._logger.log(
            log_level,
            event.message,
            extra={
                "security_event": payload,
                "event_type": event.event_type,
            },
        )

        outcome = (
            AuditOutcome.DENIED
            if event.event_type
            in {
                "login_denied",
                "access_denied",
                "permission_denied",
            }
            else AuditOutcome.SUCCESS
        )

        self._audit_logger.record(
            AuditEvent(
                action=event.event_type,
                resource_type="security",
                outcome=outcome,
                actor_id=event.actor_id,
                actor_email=event.actor_email,
                request_id=event.request_id,
                source_ip=event.source_ip,
                details=payload,
            )
        )

    @staticmethod
    def _resolve_log_level(
        severity: SecuritySeverity,
    ) -> int:
        """Map security severity to a Python logging level."""

        mapping = {
            SecuritySeverity.INFORMATIONAL: logging.INFO,
            SecuritySeverity.LOW: logging.INFO,
            SecuritySeverity.MEDIUM: logging.WARNING,
            SecuritySeverity.HIGH: logging.ERROR,
            SecuritySeverity.CRITICAL: logging.CRITICAL,
        }

        return mapping[severity]


_security_logger = SecurityLogger()


def get_security_logger() -> SecurityLogger:
    """Return the shared security logger."""

    return _security_logger