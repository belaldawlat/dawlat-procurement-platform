"""Platform integration health checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from services.integration.engine_registry import get_engine_registry
from services.integration.service_registry import get_service_registry


@dataclass(frozen=True)
class PlatformHealthReport:
    healthy: bool
    engine_count: int
    service_count: int
    disabled_engines: tuple[str, ...]
    disabled_services: tuple[str, ...]
    failures: tuple[str, ...]
    checked_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class PlatformHealth:
    def check(self) -> PlatformHealthReport:
        failures: list[str] = []

        engines = get_engine_registry().list()
        services = get_service_registry().list()

        disabled_engines = tuple(
            item.name
            for item in engines
            if not item.enabled
        )

        disabled_services = tuple(
            item.name
            for item in services
            if not item.enabled
        )

        critical_disabled = [
            item.name
            for item in services
            if item.critical and not item.enabled
        ]

        if critical_disabled:
            failures.append(
                "Critical services disabled: "
                + ", ".join(critical_disabled)
            )

        return PlatformHealthReport(
            healthy=not failures,
            engine_count=len(engines),
            service_count=len(services),
            disabled_engines=disabled_engines,
            disabled_services=disabled_services,
            failures=tuple(failures),
        )


_health = PlatformHealth()


def get_platform_health() -> PlatformHealth:
    return _health