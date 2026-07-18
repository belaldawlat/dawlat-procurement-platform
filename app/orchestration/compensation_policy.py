"""Deterministic policies for enterprise workflow compensation."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.compensation_models import (
    CompensationPlan,
    CompensationStepDefinition,
)


@dataclass(frozen=True)
class CompensationPolicyViolation:
    code: str
    message: str
    step_id: str = ""
    field_name: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip())
        object.__setattr__(self, "message", str(self.message or "").strip())
        object.__setattr__(self, "step_id", str(self.step_id or "").strip())
        object.__setattr__(self, "field_name", str(self.field_name or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))


@dataclass(frozen=True)
class CompensationPolicy:
    policy_id: str
    name: str
    reverse_execution_order: bool = True
    stop_on_unhandled_failure: bool = True
    require_idempotency_keys: bool = True
    allow_reexecution_of_successful_steps: bool = False
    maximum_total_steps: int = 100
    enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        policy_id = str(self.policy_id or "").strip()
        name = str(self.name or "").strip()
        if not policy_id:
            raise ValueError("Compensation policy ID is required.")
        if not name:
            raise ValueError("Compensation policy name is required.")
        if self.maximum_total_steps < 1:
            raise ValueError("Maximum total compensation steps must be at least 1.")
        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def validate_plan(
        self,
        plan: CompensationPlan,
    ) -> tuple[CompensationPolicyViolation, ...]:
        violations: list[CompensationPolicyViolation] = []

        if not self.enabled:
            violations.append(
                CompensationPolicyViolation(
                    code="COMPENSATION_POLICY_DISABLED",
                    message="The compensation policy is disabled.",
                )
            )

        if len(plan.steps) > self.maximum_total_steps:
            violations.append(
                CompensationPolicyViolation(
                    code="COMPENSATION_STEP_LIMIT_EXCEEDED",
                    message="The compensation plan exceeds the permitted number of steps.",
                    metadata={
                        "step_count": len(plan.steps),
                        "maximum_total_steps": self.maximum_total_steps,
                    },
                )
            )

        seen_step_ids: set[str] = set()
        seen_orders: set[int] = set()
        seen_idempotency_keys: set[str] = set()

        for step in plan.steps:
            if step.step_id in seen_step_ids:
                violations.append(
                    CompensationPolicyViolation(
                        code="DUPLICATE_COMPENSATION_STEP_ID",
                        message="A compensation step ID appears more than once.",
                        step_id=step.step_id,
                    )
                )

            if step.order in seen_orders:
                violations.append(
                    CompensationPolicyViolation(
                        code="DUPLICATE_COMPENSATION_ORDER",
                        message="Two compensation steps use the same order.",
                        step_id=step.step_id,
                        field_name="order",
                    )
                )

            if self.require_idempotency_keys:
                if not step.idempotency_key:
                    violations.append(
                        CompensationPolicyViolation(
                            code="IDEMPOTENCY_KEY_REQUIRED",
                            message="A compensation idempotency key is required.",
                            step_id=step.step_id,
                            field_name="idempotency_key",
                        )
                    )
                elif step.idempotency_key in seen_idempotency_keys:
                    violations.append(
                        CompensationPolicyViolation(
                            code="DUPLICATE_IDEMPOTENCY_KEY",
                            message="Compensation idempotency keys must be unique.",
                            step_id=step.step_id,
                            field_name="idempotency_key",
                        )
                    )

            seen_step_ids.add(step.step_id)
            seen_orders.add(step.order)
            if step.idempotency_key:
                seen_idempotency_keys.add(step.idempotency_key)

        return tuple(
            sorted(
                violations,
                key=lambda violation: (
                    violation.code,
                    violation.step_id,
                    violation.field_name,
                ),
            )
        )

    def order_steps(
        self,
        steps: tuple[CompensationStepDefinition, ...],
    ) -> tuple[CompensationStepDefinition, ...]:
        return tuple(
            sorted(
                steps,
                key=lambda step: step.order,
                reverse=self.reverse_execution_order,
            )
        )