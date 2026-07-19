"""Thread-safe persistence for enterprise plans."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_planning_models import EnterprisePlan
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


class EnterprisePlanStore:
    """Store enterprise plans with explicit create and replace semantics."""

    def __init__(self) -> None:
        self._plans: dict[str, EnterprisePlan] = {}
        self._lock = threading.RLock()

    def create(self, plan: EnterprisePlan) -> EnterprisePlan:
        if not isinstance(plan, EnterprisePlan):
            raise TypeError("Plan store requires an EnterprisePlan.")

        with self._lock:
            if plan.plan_id in self._plans:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Enterprise plan {plan.plan_id!r} already exists."
                    )
                )
            self._plans[plan.plan_id] = plan

        return plan

    def save(self, plan: EnterprisePlan) -> EnterprisePlan:
        if not isinstance(plan, EnterprisePlan):
            raise TypeError("Plan store requires an EnterprisePlan.")

        with self._lock:
            if plan.plan_id not in self._plans:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Enterprise plan {plan.plan_id!r} was not found."
                    )
                )
            self._plans[plan.plan_id] = plan

        return plan

    def upsert(self, plan: EnterprisePlan) -> EnterprisePlan:
        if not isinstance(plan, EnterprisePlan):
            raise TypeError("Plan store requires an EnterprisePlan.")

        with self._lock:
            self._plans[plan.plan_id] = plan

        return plan

    def get(self, plan_id: str) -> EnterprisePlan:
        cleaned_id = str(plan_id or "").strip()

        if not cleaned_id:
            raise ValueError("Enterprise plan ID is required.")

        with self._lock:
            plan = self._plans.get(cleaned_id)

        if plan is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise plan {cleaned_id!r} was not found."
                )
            )

        return plan

    def delete(self, plan_id: str) -> EnterprisePlan:
        cleaned_id = str(plan_id or "").strip()

        if not cleaned_id:
            raise ValueError("Enterprise plan ID is required.")

        with self._lock:
            plan = self._plans.pop(cleaned_id, None)

        if plan is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise plan {cleaned_id!r} was not found."
                )
            )

        return plan

    def contains(self, plan_id: str) -> bool:
        cleaned_id = str(plan_id or "").strip()

        with self._lock:
            return cleaned_id in self._plans

    def list_plans(self) -> tuple[EnterprisePlan, ...]:
        with self._lock:
            return tuple(
                self._plans[key]
                for key in sorted(self._plans)
            )

    def clear(self) -> None:
        with self._lock:
            self._plans.clear()


_default_enterprise_plan_store = EnterprisePlanStore()


def get_enterprise_plan_store() -> EnterprisePlanStore:
    return _default_enterprise_plan_store