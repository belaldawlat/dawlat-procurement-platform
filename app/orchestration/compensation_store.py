"""Thread-safe storage for compensation policies and plans."""

from __future__ import annotations

import threading

from app.orchestration.compensation_models import CompensationPlan
from app.orchestration.compensation_policy import CompensationPolicy
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


class InMemoryCompensationStore:
    def __init__(self) -> None:
        self._policies: dict[str, CompensationPolicy] = {}
        self._plans: dict[str, CompensationPlan] = {}
        self._idempotency_results: dict[str, object] = {}
        self._lock = threading.RLock()

    def register_policy(
        self,
        policy: CompensationPolicy,
        *,
        replace_existing: bool = False,
    ) -> CompensationPolicy:
        if not isinstance(policy, CompensationPolicy):
            raise TypeError("Compensation store requires a CompensationPolicy.")

        with self._lock:
            if policy.policy_id in self._policies and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Compensation policy {policy.policy_id!r} already exists."
                    ),
                    metadata={"policy_id": policy.policy_id},
                )
            self._policies[policy.policy_id] = policy

        return policy

    def get_policy(self, policy_id: str) -> CompensationPolicy:
        cleaned_id = self._clean_identifier(
            policy_id,
            "Compensation policy ID",
        )
        with self._lock:
            policy = self._policies.get(cleaned_id)

        if policy is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Compensation policy {cleaned_id!r} was not found."
                ),
                metadata={"policy_id": cleaned_id},
            )

        return policy

    def create_plan(self, plan: CompensationPlan) -> CompensationPlan:
        if not isinstance(plan, CompensationPlan):
            raise TypeError("Compensation store requires a CompensationPlan.")

        with self._lock:
            if plan.plan_id in self._plans:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Compensation plan {plan.plan_id!r} already exists."
                    ),
                    metadata={"plan_id": plan.plan_id},
                )
            self._plans[plan.plan_id] = plan

        return plan

    def get_plan(self, plan_id: str) -> CompensationPlan:
        cleaned_id = self._clean_identifier(
            plan_id,
            "Compensation plan ID",
        )
        with self._lock:
            plan = self._plans.get(cleaned_id)

        if plan is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Compensation plan {cleaned_id!r} was not found."
                ),
                metadata={"plan_id": cleaned_id},
            )

        return plan

    def save_plan(self, plan: CompensationPlan) -> CompensationPlan:
        if not isinstance(plan, CompensationPlan):
            raise TypeError("Compensation store requires a CompensationPlan.")

        with self._lock:
            if plan.plan_id not in self._plans:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Compensation plan {plan.plan_id!r} was not found."
                    )
                )
            self._plans[plan.plan_id] = plan

        return plan

    def list_plans(self) -> tuple[CompensationPlan, ...]:
        with self._lock:
            return tuple(
                self._plans[plan_id]
                for plan_id in sorted(self._plans)
            )

    def has_idempotency_result(self, key: str) -> bool:
        cleaned_key = self._clean_identifier(
            key,
            "Compensation idempotency key",
        )
        with self._lock:
            return cleaned_key in self._idempotency_results

    def get_idempotency_result(self, key: str) -> object:
        cleaned_key = self._clean_identifier(
            key,
            "Compensation idempotency key",
        )
        with self._lock:
            if cleaned_key not in self._idempotency_results:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Compensation idempotency result {cleaned_key!r} "
                        "was not found."
                    )
                )
            return self._idempotency_results[cleaned_key]

    def save_idempotency_result(
        self,
        key: str,
        result: object,
    ) -> None:
        cleaned_key = self._clean_identifier(
            key,
            "Compensation idempotency key",
        )
        with self._lock:
            self._idempotency_results.setdefault(cleaned_key, result)

    def clear(self) -> None:
        with self._lock:
            self._policies.clear()
            self._plans.clear()
            self._idempotency_results.clear()

    @staticmethod
    def _clean_identifier(value: str, label: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError(f"{label} is required.")
        return cleaned


_default_compensation_store = InMemoryCompensationStore()


def get_compensation_store() -> InMemoryCompensationStore:
    return _default_compensation_store