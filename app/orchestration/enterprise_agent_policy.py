"""Policy configuration for the enterprise AI agent runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseAgentPolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_runtime_agents: int = 100
    maximum_task_attempts: int = 3
    fail_closed_without_capable_agent: bool = True
    require_human_approval_for_external_side_effects: bool = True
    pause_on_agent_failure: bool = True
    allow_memory_write: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Enterprise agent policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise agent policy name is required.")
        if self.maximum_runtime_agents < 1:
            raise ValueError("Maximum runtime agents must be at least 1.")
        if self.maximum_task_attempts < 1:
            raise ValueError("Maximum task attempts must be at least 1.")

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version or "1.0.0").strip())