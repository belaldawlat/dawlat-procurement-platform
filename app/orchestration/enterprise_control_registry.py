"""Thread-safe registry for enterprise control actions."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.enterprise_control_models import (
    ControlAction,
)
from app.orchestration.exceptions import WorkflowIntegrityError


EnterpriseControlHandler = Callable[[dict[str, Any]], Any]


class EnterpriseControlRegistry:
    """Thread-safe control action-handler registry."""

    def __init__(self) -> None:
        self._handlers: dict[
            ControlAction,
            EnterpriseControlHandler,
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        action: ControlAction,
        handler: EnterpriseControlHandler,
        *,
        replace_existing: bool = False,
    ) -> None:
        if not isinstance(action, ControlAction):
            raise TypeError("Action must be a ControlAction.")

        if not callable(handler):
            raise TypeError(
                "Enterprise control handler must be callable."
            )

        with self._lock:
            if (
                action in self._handlers
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Handler for control action "
                        f"{action.value!r} already exists."
                    )
                )

            self._handlers[action] = handler

    def get(
        self,
        action: ControlAction,
    ) -> EnterpriseControlHandler:
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
        action: ControlAction,
    ) -> bool:
        with self._lock:
            return action in self._handlers

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()


_default_enterprise_control_registry = EnterpriseControlRegistry()


def get_enterprise_control_registry(
) -> EnterpriseControlRegistry:
    """Return the shared enterprise control registry."""

    return _default_enterprise_control_registry