"""Thread-safe registry for enterprise orchestration handlers."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.enterprise_models import EnterpriseCommand
from app.orchestration.exceptions import WorkflowIntegrityError


EnterpriseCommandHandler = Callable[[dict[str, Any]], Any]


class EnterpriseOrchestrationRegistry:
    """Thread-safe command-handler registry."""

    def __init__(self) -> None:
        self._handlers: dict[
            EnterpriseCommand,
            EnterpriseCommandHandler,
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        command: EnterpriseCommand,
        handler: EnterpriseCommandHandler,
        *,
        replace_existing: bool = False,
    ) -> None:
        if not isinstance(command, EnterpriseCommand):
            raise TypeError("Command must be an EnterpriseCommand.")

        if not callable(handler):
            raise TypeError(
                "Enterprise command handler must be callable."
            )

        with self._lock:
            if (
                command in self._handlers
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Handler for command {command.value!r} "
                        "already exists."
                    )
                )

            self._handlers[command] = handler

    def get(
        self,
        command: EnterpriseCommand,
    ) -> EnterpriseCommandHandler:
        with self._lock:
            handler = self._handlers.get(command)

        if handler is None:
            raise WorkflowIntegrityError(
                technical_message=(
                    f"No handler is registered for "
                    f"{command.value!r}."
                )
            )

        return handler

    def contains(
        self,
        command: EnterpriseCommand,
    ) -> bool:
        with self._lock:
            return command in self._handlers

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()


_default_enterprise_registry = EnterpriseOrchestrationRegistry()


def get_enterprise_orchestration_registry(
) -> EnterpriseOrchestrationRegistry:
    return _default_enterprise_registry