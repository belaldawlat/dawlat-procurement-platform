"""Enterprise AI agent runtime."""

from __future__ import annotations

from dataclasses import replace

from app.orchestration.enterprise_agent_coordinator import (
    EnterpriseAgentCoordinator,
)
from app.orchestration.enterprise_agent_executor import (
    EnterpriseAgentExecutor,
)
from app.orchestration.enterprise_agent_memory import (
    EnterpriseAgentMemory,
)
from app.orchestration.enterprise_agent_models import (
    EnterpriseAgentTask,
    EnterpriseAgentTaskStatus,
)
from app.orchestration.enterprise_agent_policy import (
    EnterpriseAgentPolicy,
)
from app.orchestration.enterprise_agent_result import (
    EnterpriseAgentRuntimeResult,
)
from app.orchestration.enterprise_agent_registry import (
    EnterpriseAgentRegistry,
)


class EnterpriseAgentRuntime:
    """Coordinate assignment, execution, memory and failure controls."""

    def __init__(
        self,
        *,
        policy: EnterpriseAgentPolicy | None = None,
        registry: EnterpriseAgentRegistry | None = None,
        memory: EnterpriseAgentMemory | None = None,
        coordinator: EnterpriseAgentCoordinator | None = None,
        executor: EnterpriseAgentExecutor | None = None,
    ) -> None:
        self._policy = policy or EnterpriseAgentPolicy(
            policy_id="default-enterprise-agent-runtime",
            name="Default Enterprise Agent Runtime Policy",
        )
        self._registry = registry or EnterpriseAgentRegistry()
        self._memory = memory or EnterpriseAgentMemory()
        self._coordinator = coordinator or EnterpriseAgentCoordinator(
            registry=self._registry,
        )
        self._executor = executor or EnterpriseAgentExecutor()

    @property
    def policy(self) -> EnterpriseAgentPolicy:
        return self._policy

    @property
    def registry(self) -> EnterpriseAgentRegistry:
        return self._registry

    @property
    def memory(self) -> EnterpriseAgentMemory:
        return self._memory

    def run(
        self,
        tasks: tuple[EnterpriseAgentTask, ...],
    ) -> EnterpriseAgentRuntimeResult:
        if not self._policy.enabled:
            raise ValueError(
                "Enterprise agent runtime policy is disabled."
            )

        if len(self._registry.list_agents()) > (
            self._policy.maximum_runtime_agents
        ):
            raise ValueError(
                "Registered agent count exceeds runtime policy."
            )

        ordered_tasks = tuple(
            sorted(
                tasks,
                key=lambda task: (
                    -task.priority,
                    task.created_at,
                    task.task_id,
                ),
            )
        )

        completed = []
        failed = []
        blocked = []

        for task in ordered_tasks:
            if task.is_terminal:
                continue

            prepared_task = replace(
                task,
                maximum_attempts=min(
                    task.maximum_attempts,
                    self._policy.maximum_task_attempts,
                ),
            )

            assignment = self._coordinator.assign(
                prepared_task
            )

            if assignment is None:
                blocked_task = replace(
                    prepared_task,
                    status=EnterpriseAgentTaskStatus.BLOCKED,
                )
                blocked.append(blocked_task)
                continue

            assigned_task, handler = assignment

            try:
                result = self._executor.execute(
                    assigned_task,
                    handler,
                )
            finally:
                self._coordinator.release(
                    assigned_task.assigned_agent_id
                )

            if result.successful:
                completed.append(result)

                if self._policy.allow_memory_write:
                    self._memory.write(
                        assigned_task.assigned_agent_id,
                        assigned_task.task_id,
                        result.output,
                    )
            else:
                failed.append(result)

        return EnterpriseAgentRuntimeResult(
            completed=tuple(completed),
            failed=tuple(failed),
            blocked_tasks=tuple(blocked),
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "task_count": len(tasks),
                "agent_count": len(
                    self._registry.list_agents()
                ),
            },
        )


_default_enterprise_agent_runtime = EnterpriseAgentRuntime()


def get_enterprise_agent_runtime() -> EnterpriseAgentRuntime:
    return _default_enterprise_agent_runtime