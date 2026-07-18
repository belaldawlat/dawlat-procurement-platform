"""Autonomous Brain Monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable


class BrainAlertSeverity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class BrainComponentStatus:
    component_name: str
    healthy: bool
    latency_ms: float
    error_count: int
    confidence_score: int
    stale_minutes: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrainAlert:
    component_name: str
    severity: BrainAlertSeverity
    title: str
    description: str
    blocking: bool


@dataclass(frozen=True)
class BrainHealthReport:
    healthy: bool
    health_score: int
    components_checked: int
    alerts: tuple[BrainAlert, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class AutonomousBrainMonitor:
    """Monitor engine health, latency, drift and data freshness."""

    def evaluate(
        self,
        components: Iterable[BrainComponentStatus],
    ) -> BrainHealthReport:
        component_list = list(components)
        alerts: list[BrainAlert] = []

        if not component_list:
            return BrainHealthReport(
                healthy=False,
                health_score=0,
                components_checked=0,
                alerts=(
                    BrainAlert(
                        component_name="Autonomous Brain",
                        severity=BrainAlertSeverity.CRITICAL,
                        title="No components reported",
                        description=(
                            "The autonomous brain has no health telemetry."
                        ),
                        blocking=True,
                    ),
                ),
            )

        scores: list[int] = []

        for component in component_list:
            score = 100

            if not component.healthy:
                score -= 50
                alerts.append(
                    BrainAlert(
                        component_name=component.component_name,
                        severity=BrainAlertSeverity.CRITICAL,
                        title="Component unhealthy",
                        description=(
                            "The component reported an unhealthy state."
                        ),
                        blocking=True,
                    )
                )

            if component.latency_ms > 5000:
                score -= 25
                alerts.append(
                    BrainAlert(
                        component_name=component.component_name,
                        severity=BrainAlertSeverity.HIGH,
                        title="Severe latency",
                        description=(
                            f"Latency is {component.latency_ms:.0f} ms."
                        ),
                        blocking=False,
                    )
                )
            elif component.latency_ms > 1500:
                score -= 10

            if component.error_count > 0:
                score -= min(
                    30,
                    component.error_count * 5,
                )

            if component.confidence_score < 50:
                score -= 20
                alerts.append(
                    BrainAlert(
                        component_name=component.component_name,
                        severity=BrainAlertSeverity.HIGH,
                        title="Confidence degradation",
                        description=(
                            "Model or engine confidence is below threshold."
                        ),
                        blocking=False,
                    )
                )

            if component.stale_minutes > 60:
                score -= 20
                alerts.append(
                    BrainAlert(
                        component_name=component.component_name,
                        severity=BrainAlertSeverity.WARNING,
                        title="Stale data",
                        description=(
                            f"Data is {component.stale_minutes} minute(s) old."
                        ),
                        blocking=False,
                    )
                )

            scores.append(
                max(0, min(100, score))
            )

        health_score = round(
            sum(scores) / len(scores)
        )
        healthy = (
            health_score >= 70
            and not any(
                alert.blocking
                for alert in alerts
            )
        )

        return BrainHealthReport(
            healthy=healthy,
            health_score=health_score,
            components_checked=len(component_list),
            alerts=tuple(alerts),
        )


_monitor = AutonomousBrainMonitor()


def get_autonomous_brain_monitor() -> AutonomousBrainMonitor:
    return _monitor