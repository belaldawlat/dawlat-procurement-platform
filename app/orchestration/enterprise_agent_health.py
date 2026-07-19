"""Health evaluation for enterprise AI agents."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.enterprise_agent_models import (
    EnterpriseAgentDefinition,
    EnterpriseAgentStatus,
)


@dataclass(frozen=True)
class EnterpriseAgentHealthResult:
    agent_id: str
    healthy: bool
    status: EnterpriseAgentStatus
    reason: str


class EnterpriseAgentHealth:
    """Evaluate whether an agent may receive work."""

    def evaluate(
        self,
        agent: EnterpriseAgentDefinition,
        active_tasks: int,
    ) -> EnterpriseAgentHealthResult:
        if active_tasks < 0:
            raise ValueError("Active task count cannot be negative.")

        if agent.status in {
            EnterpriseAgentStatus.FAILED,
            EnterpriseAgentStatus.DISABLED,
            EnterpriseAgentStatus.PAUSED,
        }:
            return EnterpriseAgentHealthResult(
                agent_id=agent.agent_id,
                healthy=False,
                status=agent.status,
                reason="Agent status does not permit execution.",
            )

        if active_tasks >= agent.maximum_concurrency:
            return EnterpriseAgentHealthResult(
                agent_id=agent.agent_id,
                healthy=False,
                status=EnterpriseAgentStatus.DEGRADED,
                reason="Agent concurrency capacity is exhausted.",
            )

        return EnterpriseAgentHealthResult(
            agent_id=agent.agent_id,
            healthy=True,
            status=agent.status,
            reason="Agent is available for execution.",
        )