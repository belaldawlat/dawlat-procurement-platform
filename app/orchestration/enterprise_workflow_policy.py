"""Governance policy for enterprise workflow intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseWorkflowPolicy:
    """Immutable workflow governance and safety controls."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_stages: int = 100
    maximum_tasks_per_stage: int = 200
    maximum_stage_dependency_depth: int = 50
    maximum_task_dependency_depth: int = 100
    maximum_task_attempts: int = 5
    maximum_task_timeout_seconds: int = 3_600
    approvals_enabled: bool = True
    versioning_enabled: bool = True
    analytics_enabled: bool = True
    enforce_template_immutability: bool = True
    fail_closed_on_validation_error: bool = True
    allow_stage_skipping: bool = False
    allow_workflow_reactivation: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Workflow policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Workflow policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Workflow policy version is required.")
        if self.maximum_stages < 1:
            raise ValueError("Maximum workflow stages must be at least 1.")
        if self.maximum_tasks_per_stage < 1:
            raise ValueError(
                "Maximum tasks per stage must be at least 1."
            )
        if self.maximum_stage_dependency_depth < 1:
            raise ValueError(
                "Maximum stage dependency depth must be at least 1."
            )
        if self.maximum_task_dependency_depth < 1:
            raise ValueError(
                "Maximum task dependency depth must be at least 1."
            )
        if self.maximum_task_attempts < 1:
            raise ValueError(
                "Maximum task attempts must be at least 1."
            )
        if self.maximum_task_timeout_seconds < 1:
            raise ValueError(
                "Maximum task timeout must be at least one second."
            )

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())