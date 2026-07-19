"""Thread-safe registry for enterprise AI agents and handlers."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.enterprise_agent_models import (
    EnterpriseAgentDefinition,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


EnterpriseAgentHandler = Callable[[dict[str, Any]], dict[str, Any]]


class EnterpriseAgentRegistry:
    """Store agent definitions and execution handlers."""

    def __init__(self) -> None:
        self._agents: dict[
            str,
            tuple[EnterpriseAgentDefinition, EnterpriseAgentHandler],
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        agent: EnterpriseAgentDefinition,
        handler: EnterpriseAgentHandler,
        *,
        replace_existing: bool = False,
    ) -> EnterpriseAgentDefinition:
        if not isinstance(agent, EnterpriseAgentDefinition):
            raise TypeError(
                "Registry requires an EnterpriseAgentDefinition."
            )
        if not callable(handler):
            raise TypeError("Enterprise agent handler must be callable.")

        with self._lock:
            if (
                agent.agent_id in self._agents
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Enterprise agent "
                        f"{agent.agent_id!r} already exists."
                    )
                )

            self._agents[agent.agent_id] = (agent, handler)

        return agent

    def get(
        self,
        agent_id: str,
    ) -> tuple[EnterpriseAgentDefinition, EnterpriseAgentHandler]:
        cleaned_id = str(agent_id or "").strip()

        if not cleaned_id:
            raise ValueError("Enterprise agent ID is required.")

        with self._lock:
            item = self._agents.get(cleaned_id)

        if item is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise agent {cleaned_id!r} was not found."
                )
            )

        return item

    def list_agents(
        self,
    ) -> tuple[
        tuple[EnterpriseAgentDefinition, EnterpriseAgentHandler],
        ...,
    ]:
        with self._lock:
            return tuple(
                self._agents[key]
                for key in sorted(self._agents)
            )

    def clear(self) -> None:
        with self._lock:
            self._agents.clear()


_default_enterprise_agent_registry = EnterpriseAgentRegistry()


def get_enterprise_agent_registry() -> EnterpriseAgentRegistry:
    return _default_enterprise_agent_registry