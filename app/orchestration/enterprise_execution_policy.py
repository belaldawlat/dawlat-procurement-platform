"""Policy controls for enterprise execution intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseExecutionPolicy:
    """Immutable governance and safety controls."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_execution_steps: int = 500
    maximum_dependency_depth: int = 100
    maximum_step_attempts: int = 5
    maximum_step_timeout_seconds: int = 3_600
    maximum_parallel_steps: int = 20
    checkpoint_after_each_step: bool = True
    emit_events: bool = True
    telemetry_enabled: bool = True
    fail_closed_on_validation_error: bool = True
    pause_on_external_side_effect: bool = True
    require_human_approval_for_financial_side_effects: bool = True
    recover_failed_steps: bool = True
    compensate_on_terminal_failure: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError(
                "Enterprise execution policy ID is required."
            )
        if not str(self.name or "").strip():
            raise ValueError(
                "Enterprise execution policy name is required."
            )
        if not str(self.version or "").strip():
            raise ValueError(
                "Enterprise execution policy version is required."
            )
        if self.maximum_execution_steps < 1:
            raise ValueError(
                "Maximum execution steps must be at least 1."
            )
        if self.maximum_dependency_depth < 1:
            raise ValueError(
                "Maximum execution dependency depth must be at least 1."
            )
        if self.maximum_step_attempts < 1:
            raise ValueError(
                "Maximum step attempts must be at least 1."
            )
        if self.maximum_step_timeout_seconds < 1:
            raise ValueError(
                "Maximum step timeout must be at least one second."
            )
        if self.maximum_parallel_steps < 1:
            raise ValueError(
                "Maximum parallel steps must be at least 1."
            )

        object.__setattr__(
            self,
            "policy_id",
            str(self.policy_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "version",
            str(self.version).strip(),
        )