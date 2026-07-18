"""Registry for enterprise application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServiceRegistration:
    name: str
    service: Any
    domain: str
    critical: bool = False
    enabled: bool = True


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, ServiceRegistration] = {}

    def register(
        self,
        *,
        name: str,
        service: Any,
        domain: str,
        critical: bool = False,
        enabled: bool = True,
    ) -> ServiceRegistration:
        registration = ServiceRegistration(
            name=name,
            service=service,
            domain=domain,
            critical=critical,
            enabled=enabled,
        )
        self._services[name] = registration
        return registration

    def get(self, name: str) -> Any:
        registration = self._services.get(name)
        if registration is None:
            raise LookupError(f"Service '{name}' is not registered.")
        if not registration.enabled:
            raise RuntimeError(f"Service '{name}' is disabled.")
        return registration.service

    def list(self) -> tuple[ServiceRegistration, ...]:
        return tuple(self._services.values())


_registry = ServiceRegistry()


def get_service_registry() -> ServiceRegistry:
    return _registry