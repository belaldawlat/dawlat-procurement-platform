"""Safe execution adapter for enterprise AI agents."""

from __future__ import annotations

from dataclasses import replace

from app.orchestration.enterprise_agent_models import (
    EnterpriseAgentTask,
    EnterpriseAgentTaskStatus,
)
from app.orchestration.enterprise_agent_result import (
    EnterpriseAgentExecutionResult,
)
from app.orchestration.enterprise_agent_registry import (
    EnterpriseAgentHandler,
)


class EnterpriseAgentExecutor:
    """Execute one agent task and capture a deterministic result."""

    def execute(
        self,
        task: EnterpriseAgentTask,
        handler: EnterpriseAgentHandler,
    ) -> EnterpriseAgentExecutionResult:
        running_task = replace(
            task,
            status=EnterpriseAgentTaskStatus.RUNNING,
            attempts=task.attempts + 1,
        )

        try:
            output = handler(running_task.as_dict())

            if not isinstance(output, dict):
                raise TypeError(
                    "Enterprise agent handlers must return a dictionary."
                )

            completed_task = replace(
                running_task,
                status=EnterpriseAgentTaskStatus.COMPLETED,
            )

            return EnterpriseAgentExecutionResult(
                task=completed_task,
                successful=True,
                output=output,
            )
        except Exception as exc:
            terminal_status = (
                EnterpriseAgentTaskStatus.FAILED
                if running_task.attempts
                >= running_task.maximum_attempts
                else EnterpriseAgentTaskStatus.BLOCKED
            )

            failed_task = replace(
                running_task,
                status=terminal_status,
            )

            return EnterpriseAgentExecutionResult(
                task=failed_task,
                successful=False,
                output={},
                error=str(exc),
            )