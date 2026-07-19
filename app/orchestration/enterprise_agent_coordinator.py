"""Task assignment for enterprise AI agents."""

from __future__ import annotations

from dataclasses import replace

from app.orchestration.enterprise_agent_health import (
    EnterpriseAgentHealth,
)
from app.orchestration.enterprise_agent_models import (
    EnterpriseAgentTask,
    EnterpriseAgentTaskStatus,
)
from app.orchestration.enterprise_agent_registry import (
    EnterpriseAgentHandler,
    EnterpriseAgentRegistry,
)


class EnterpriseAgentCoordinator:
    """Select the best healthy capable agent."""

    def __init__(
        self,
        registry: EnterpriseAgentRegistry | None = None,
        health: EnterpriseAgentHealth | None = None,
    ) -> None:
        self._registry = registry or EnterpriseAgentRegistry()
        self._health = health or EnterpriseAgentHealth()
        self._active_tasks: dict[str, int] = {}

    @property
    def registry(self) -> EnterpriseAgentRegistry:
        return self._registry

    def assign(
        self,
        task: EnterpriseAgentTask,
    ) -> tuple[
        EnterpriseAgentTask,
        EnterpriseAgentHandler,
    ] | None:
        candidates = []

        for agent, handler in self._registry.list_agents():
            if task.capability not in agent.capabilities:
                continue

            active_tasks = self._active_tasks.get(
                agent.agent_id,
                0,
            )
            health = self._health.evaluate(
                agent,
                active_tasks,
            )

            if not health.healthy:
                continue

            candidates.append(
                (
                    active_tasks,
                    -agent.maximum_concurrency,
                    agent.agent_id,
                    agent,
                    handler,
                )
            )

        if not candidates:
            return None

        _, _, _, agent, handler = min(candidates)

        self._active_tasks[agent.agent_id] = (
            self._active_tasks.get(agent.agent_id, 0) + 1
        )

        assigned_task = replace(
            task,
            assigned_agent_id=agent.agent_id,
            status=EnterpriseAgentTaskStatus.ASSIGNED,
        )

        return assigned_task, handler

    def release(self, agent_id: str) -> None:
        cleaned_id = str(agent_id or "").strip()
        current = self._active_tasks.get(cleaned_id, 0)

        if current <= 1:
            self._active_tasks.pop(cleaned_id, None)
        else:
            self._active_tasks[cleaned_id] = current - 1