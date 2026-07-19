"""Thread-safe registry for autonomous procurement action handlers."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.autonomous_procurement_models import AutonomousAction
from app.orchestration.exceptions import WorkflowIntegrityError


AutonomousActionHandler = Callable[[dict[str, Any]], Any]


class AutonomousProcurementRegistry:
    """Thread-safe action-handler registry."""

    def __init__(self) -> None:
        self._handlers: dict[
            AutonomousAction,
            AutonomousActionHandler,
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        action: AutonomousAction,
        handler: AutonomousActionHandler,
        *,
        replace_existing: bool = False,
    ) -> None:
        if not isinstance(action, AutonomousAction):
            raise TypeError("Action must be an AutonomousAction.")

        if not callable(handler):
            raise TypeError(
                "Autonomous action handler must be callable."
            )

        with self._lock:
            if action in self._handlers and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Handler for action {action.value!r} "
                        "already exists."
                    )
                )

            self._handlers[action] = handler

    def get(
        self,
        action: AutonomousAction,
    ) -> AutonomousActionHandler:
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

    def contains(
        self,
        action: AutonomousAction,
    ) -> bool:
        with self._lock:
            return action in self._handlers

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()


_default_autonomous_procurement_registry = (
    AutonomousProcurementRegistry()
)


def get_autonomous_procurement_registry(
) -> AutonomousProcurementRegistry:
    return _default_autonomous_procurement_registry