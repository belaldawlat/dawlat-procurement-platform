"""Results produced by the enterprise command center."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_command_models import (
    CommandCenterHealth,
    ExecutiveDirective,
    ExecutiveKPI,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseCommandResult:
    """Immutable command-center result."""

    portfolio_id: str
    health: CommandCenterHealth
    health_score: float
    kpis: tuple[ExecutiveKPI, ...]
    directives: tuple[ExecutiveDirective, ...]
    execution_paused: bool
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.portfolio_id or "").strip():
            raise ValueError("Portfolio ID is required.")

        if not 0 <= self.health_score <= 100:
            raise ValueError(
                "Command-center health score must be between 0 and 100."
            )

        object.__setattr__(
            self,
            "portfolio_id",
            str(self.portfolio_id).strip(),
        )
        object.__setattr__(self, "kpis", tuple(self.kpis))
        object.__setattr__(self, "directives", tuple(self.directives))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
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
    def critical_directives(self) -> tuple[ExecutiveDirective, ...]:
        return tuple(
            directive
            for directive in self.directives
            if directive.priority.value == "critical"
        )

    @property
    def blocking_directives(self) -> tuple[ExecutiveDirective, ...]:
        return tuple(
            directive
            for directive in self.directives
            if directive.blocking
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "health": self.health.value,
            "health_score": self.health_score,
            "execution_paused": self.execution_paused,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "critical_directive_count": len(self.critical_directives),
            "blocking_directive_count": len(self.blocking_directives),
            "metadata": redact_mapping(self.metadata),
            "kpis": [kpi.as_dict() for kpi in self.kpis],
            "directives": [
                directive.as_dict()
                for directive in self.directives
            ],
        }