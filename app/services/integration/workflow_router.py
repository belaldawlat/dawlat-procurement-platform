"""Workflow router for enterprise business actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from services.integration.execution_context import ExecutionContext


@dataclass(frozen=True)
class WorkflowRoute:
    action_name: str
    handler_name: str


class WorkflowRouter:
    def __init__(self) -> None:
        self._routes: dict[
            str,
            Callable[[ExecutionContext, dict[str, Any]], Any],
        ] = {}

    def register(
        self,
        action_name: str,
        handler: Callable[
            [ExecutionContext, dict[str, Any]],
            Any,
        ],
    ) -> WorkflowRoute:
        self._routes[action_name] = handler
        return WorkflowRoute(
            action_name=action_name,
            handler_name=handler.__name__,
        )

    def route(
        self,
        action_name: str,
        context: ExecutionContext,
        payload: dict[str, Any],
    ) -> Any:
        handler = self._routes.get(action_name)
        if handler is None:
            raise LookupError(
                f"No workflow route exists for '{action_name}'."
            )
        return handler(context, payload)

    def routes(self) -> tuple[WorkflowRoute, ...]:
        return tuple(
            WorkflowRoute(
                action_name=name,
                handler_name=handler.__name__,
            )
            for name, handler in self._routes.items()
        )


_router = WorkflowRouter()


def get_workflow_router() -> WorkflowRouter:
    return _router