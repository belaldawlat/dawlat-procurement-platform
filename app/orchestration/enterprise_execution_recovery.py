"""Recovery and compensation for enterprise execution intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.orchestration.enterprise_execution_models import (
    EnterpriseExecutionStep,
    EnterpriseExecutionStepStatus,
)
from app.orchestration.enterprise_execution_policy import (
    EnterpriseExecutionPolicy,
)


EnterpriseExecutionRecoveryHandler = Callable[
    [EnterpriseExecutionStep],
    dict[str, Any],
]


@dataclass(frozen=True)
class EnterpriseExecutionRecoveryResult:
    step: EnterpriseExecutionStep
    recovered: bool
    compensated: bool
    retry_allowed: bool
    output: dict[str, Any]
    error: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", dict(self.output))
        object.__setattr__(self, "error", str(self.error or "").strip())

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.as_dict(),
            "recovered": self.recovered,
            "compensated": self.compensated,
            "retry_allowed": self.retry_allowed,
            "output": dict(self.output),
            "error": self.error,
        }


class EnterpriseExecutionRecovery:
    def recover(
        self,
        *,
        step: EnterpriseExecutionStep,
        policy: EnterpriseExecutionPolicy,
        retry_handler: EnterpriseExecutionRecoveryHandler | None = None,
        compensation_handler: EnterpriseExecutionRecoveryHandler | None = None,
    ) -> EnterpriseExecutionRecoveryResult:
        retry_allowed = (
            policy.recover_failed_steps
            and step.attempts < min(
                step.maximum_attempts,
                policy.maximum_step_attempts,
            )
        )

        if retry_allowed and retry_handler is not None:
            try:
                output = retry_handler(step)

                if not isinstance(output, dict):
                    raise TypeError(
                        "Recovery handlers must return a dictionary."
                    )

                return EnterpriseExecutionRecoveryResult(
                    step=step,
                    recovered=True,
                    compensated=False,
                    retry_allowed=True,
                    output=output,
                )
            except Exception as exc:
                retry_error = str(exc)
            else:
                retry_error = ""
        else:
            retry_error = ""

        if (
            policy.compensate_on_terminal_failure
            and compensation_handler is not None
        ):
            try:
                output = compensation_handler(step)

                if not isinstance(output, dict):
                    raise TypeError(
                        "Compensation handlers must return a dictionary."
                    )

                return EnterpriseExecutionRecoveryResult(
                    step=step,
                    recovered=False,
                    compensated=True,
                    retry_allowed=retry_allowed,
                    output=output,
                    error=retry_error,
                )
            except Exception as exc:
                return EnterpriseExecutionRecoveryResult(
                    step=step,
                    recovered=False,
                    compensated=False,
                    retry_allowed=retry_allowed,
                    output={},
                    error=str(exc),
                )

        return EnterpriseExecutionRecoveryResult(
            step=step,
            recovered=False,
            compensated=False,
            retry_allowed=retry_allowed,
            output={},
            error=retry_error,
        )

    @staticmethod
    def terminal_status(
        result: EnterpriseExecutionRecoveryResult,
    ) -> EnterpriseExecutionStepStatus:
        if result.recovered:
            return EnterpriseExecutionStepStatus.SUCCEEDED
        if result.compensated:
            return EnterpriseExecutionStepStatus.COMPENSATED
        return EnterpriseExecutionStepStatus.FAILED