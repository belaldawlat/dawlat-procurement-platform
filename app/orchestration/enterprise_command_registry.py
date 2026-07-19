"""Thread-safe registry for executive command handlers."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.enterprise_command_models import ExecutiveAction
from app.orchestration.exceptions import WorkflowIntegrityError


ExecutiveCommandHandler = Callable[[dict[str, Any]], Any]


class EnterpriseCommandRegistry:
    """Thread-safe executive action registry."""

    def __init__(self) -> None:
        self._handlers: dict[
            ExecutiveAction,
            ExecutiveCommandHandler,
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        action: ExecutiveAction,
        handler: ExecutiveCommandHandler,
        *,
        replace_existing: bool = False,
    ) -> None:
        if not isinstance(action, ExecutiveAction):
            raise TypeError("Action must be an ExecutiveAction.")
        if not callable(handler):
            raise TypeError(
                "Executive command handler must be callable."
            )

        with self._lock:
            if action in self._handlers and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Handler for executive action "
                        f"{action.value!r} already exists."
                    )
                )

            self._handlers[action] = handler

    def get(
        self,
        action: ExecutiveAction,
    ) -> ExecutiveCommandHandler:
        with self._lock:
            handler = self._handlers.get(action)

        if handler is None:
            raise WorkflowIntegrityError(
                technical_message=(
                    f"No handler is registered for "
                    f"{action.value!r}."
                )
            )

        return handler

    def contains(self, action: ExecutiveAction) -> bool:
        with self._lock:
            return action in self._handlers

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()


_default_enterprise_command_registry = EnterpriseCommandRegistry()


def get_enterprise_command_registry() -> EnterpriseCommandRegistry:
    return _default_enterprise_command_registry