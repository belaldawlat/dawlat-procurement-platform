"""Registry for intelligence and decision engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EngineRegistration:
    name: str
    engine: Any
    category: str
    version: str
    enabled: bool = True


class EngineRegistry:
    def __init__(self) -> None:
        self._engines: dict[str, EngineRegistration] = {}

    def register(
        self,
        *,
        name: str,
        engine: Any,
        category: str,
        version: str = "1.0.0",
        enabled: bool = True,
    ) -> EngineRegistration:
        registration = EngineRegistration(
            name=name,
            engine=engine,
            category=category,
            version=version,
            enabled=enabled,
        )
        self._engines[name] = registration
        return registration

    def get(self, name: str) -> Any:
        registration = self._engines.get(name)
        if registration is None:
            raise LookupError(f"Engine '{name}' is not registered.")
        if not registration.enabled:
            raise RuntimeError(f"Engine '{name}' is disabled.")
        return registration.engine

    def list(self) -> tuple[EngineRegistration, ...]:
        return tuple(self._engines.values())

    def disable(self, name: str) -> None:
        registration = self._engines.get(name)
        if registration is None:
            raise LookupError(f"Engine '{name}' is not registered.")
        self._engines[name] = EngineRegistration(
            name=registration.name,
            engine=registration.engine,
            category=registration.category,
            version=registration.version,
            enabled=False,
        )


_registry = EngineRegistry()


def get_engine_registry() -> EngineRegistry:
    return _registry