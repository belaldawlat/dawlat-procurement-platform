"""Results produced by the enterprise control tower."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_control_models import (
    ControlHealth,
    EnterpriseControlAlert,
    EnterpriseControlMetric,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseControlResult:
    """Immutable control-tower evaluation result."""

    case_id: str
    health: ControlHealth
    health_score: float
    metrics: tuple[EnterpriseControlMetric, ...]
    alerts: tuple[EnterpriseControlAlert, ...]
    execution_blocked: bool
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Control result case ID is required.")

        if not 0 <= self.health_score <= 100:
            raise ValueError(
                "Control health score must be between 0 and 100."
            )

        object.__setattr__(
            self,
            "case_id",
            str(self.case_id).strip(),
        )
        object.__setattr__(
            self,
            "metrics",
            tuple(self.metrics),
        )
        object.__setattr__(
            self,
            "alerts",
            tuple(self.alerts),
        )
        object.__setattr__(
            self,
            "policy_id",
            str(self.policy_id or "").strip(),
        )
        object.__setattr__(
            self,
            "policy_version",
            str(self.policy_version or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def critical_alerts(
        self,
    ) -> tuple[EnterpriseControlAlert, ...]:
        """Return critical alerts."""

        return tuple(
            alert
            for alert in self.alerts
            if alert.priority.value == "critical"
        )

    @property
    def blocking_alerts(
        self,
    ) -> tuple[EnterpriseControlAlert, ...]:
        """Return blocking alerts."""

        return tuple(
            alert
            for alert in self.alerts
            if alert.blocking
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "case_id": self.case_id,
            "health": self.health.value,
            "health_score": self.health_score,
            "execution_blocked": self.execution_blocked,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "critical_alert_count": len(self.critical_alerts),
            "blocking_alert_count": len(self.blocking_alerts),
            "metadata": redact_mapping(self.metadata),
            "metrics": [
                metric.as_dict()
                for metric in self.metrics
            ],
            "alerts": [
                alert.as_dict()
                for alert in self.alerts
            ],
        }