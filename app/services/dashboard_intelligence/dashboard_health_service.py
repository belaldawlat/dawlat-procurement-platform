"""Dashboard subsystem health intelligence."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable

class DashboardHealthLevel(str, Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"
    CRITICAL = "Critical"

@dataclass(frozen=True)
class DashboardDependencyStatus:
    name: str
    category: str
    available: bool
    latency_ms: float
    error_count: int
    stale_minutes: int
    critical: bool

@dataclass(frozen=True)
class DashboardHealthSnapshot:
    level: DashboardHealthLevel
    health_score: int
    dependencies_checked: int
    unavailable_dependencies: tuple[str, ...]
    critical_failures: tuple[str, ...]
    latency_warnings: tuple[str, ...]
    stale_dependencies: tuple[str, ...]
    dashboard_rendering_allowed: bool
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class DashboardHealthService:
    def evaluate(
        self,
        dependencies: Iterable[DashboardDependencyStatus],
    ) -> DashboardHealthSnapshot:
        items = list(dependencies)

        if not items:
            return DashboardHealthSnapshot(
                level=DashboardHealthLevel.CRITICAL,
                health_score=0,
                dependencies_checked=0,
                unavailable_dependencies=(),
                critical_failures=("No dashboard dependencies reported.",),
                latency_warnings=(),
                stale_dependencies=(),
                dashboard_rendering_allowed=False,
            )

        scores: list[int] = []
        unavailable: list[str] = []
        critical_failures: list[str] = []
        latency_warnings: list[str] = []
        stale: list[str] = []

        for item in items:
            score = 100

            if not item.available:
                score -= 60
                unavailable.append(item.name)
                if item.critical:
                    critical_failures.append(
                        f"Critical dependency unavailable: {item.name}"
                    )

            if item.latency_ms >= 5000:
                score -= 25
                latency_warnings.append(
                    f"{item.name} latency is critically high."
                )
            elif item.latency_ms >= 1500:
                score -= 10
                latency_warnings.append(
                    f"{item.name} latency is elevated."
                )

            if item.error_count:
                score -= min(30, item.error_count * 5)

            if item.stale_minutes >= 60:
                score -= 15
                stale.append(item.name)

            scores.append(max(0, min(100, score)))

        health_score = round(sum(scores) / len(scores))

        if critical_failures:
            level = DashboardHealthLevel.CRITICAL
        elif health_score < 50:
            level = DashboardHealthLevel.UNHEALTHY
        elif health_score < 75:
            level = DashboardHealthLevel.DEGRADED
        else:
            level = DashboardHealthLevel.HEALTHY

        return DashboardHealthSnapshot(
            level=level,
            health_score=health_score,
            dependencies_checked=len(items),
            unavailable_dependencies=tuple(unavailable),
            critical_failures=tuple(critical_failures),
            latency_warnings=tuple(latency_warnings),
            stale_dependencies=tuple(stale),
            dashboard_rendering_allowed=(
                level != DashboardHealthLevel.CRITICAL
            ),
        )

_service = DashboardHealthService()

def get_dashboard_health_service() -> DashboardHealthService:
    return _service