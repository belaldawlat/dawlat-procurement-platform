"""Thread-safe persistence for Package T enterprise decisions."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_decision_result import (
    EnterpriseDecisionEngineResult,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


class EnterpriseDecisionStore:
    """Persist immutable enterprise decision results."""

    def __init__(self) -> None:
        self._decisions: dict[str, EnterpriseDecisionEngineResult] = {}
        self._case_index: dict[str, list[str]] = {}
        self._lock = threading.RLock()

    def create(
        self,
        decision: EnterpriseDecisionEngineResult,
    ) -> EnterpriseDecisionEngineResult:
        """Create a new enterprise decision."""

        if not isinstance(decision, EnterpriseDecisionEngineResult):
            raise TypeError(
                "Decision store requires an "
                "EnterpriseDecisionEngineResult."
            )

        with self._lock:
            if decision.decision_id in self._decisions:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Enterprise decision "
                        f"{decision.decision_id!r} already exists."
                    )
                )

            self._decisions[decision.decision_id] = decision
            self._case_index.setdefault(
                decision.case_id,
                [],
            ).append(decision.decision_id)

        return decision

    def save(
        self,
        decision: EnterpriseDecisionEngineResult,
    ) -> EnterpriseDecisionEngineResult:
        """Replace an existing decision."""

        if not isinstance(decision, EnterpriseDecisionEngineResult):
            raise TypeError(
                "Decision store requires an "
                "EnterpriseDecisionEngineResult."
            )

        with self._lock:
            if decision.decision_id not in self._decisions:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Enterprise decision "
                        f"{decision.decision_id!r} was not found."
                    )
                )

            current = self._decisions[decision.decision_id]

            if current.case_id != decision.case_id:
                raise WorkflowIntegrityError(
                    technical_message=(
                        "Enterprise decision case ID cannot be changed."
                    )
                )

            self._decisions[decision.decision_id] = decision

        return decision

    def upsert(
        self,
        decision: EnterpriseDecisionEngineResult,
    ) -> EnterpriseDecisionEngineResult:
        """Create or replace a decision."""

        if not isinstance(decision, EnterpriseDecisionEngineResult):
            raise TypeError(
                "Decision store requires an "
                "EnterpriseDecisionEngineResult."
            )

        with self._lock:
            existing = self._decisions.get(decision.decision_id)

            if existing is None:
                self._case_index.setdefault(
                    decision.case_id,
                    [],
                ).append(decision.decision_id)
            elif existing.case_id != decision.case_id:
                raise WorkflowIntegrityError(
                    technical_message=(
                        "Enterprise decision case ID cannot be changed."
                    )
                )

            self._decisions[decision.decision_id] = decision

        return decision

    def get(
        self,
        decision_id: str,
    ) -> EnterpriseDecisionEngineResult:
        """Return one decision by ID."""

        cleaned_id = str(decision_id or "").strip()

        if not cleaned_id:
            raise ValueError("Enterprise decision ID is required.")

        with self._lock:
            decision = self._decisions.get(cleaned_id)

        if decision is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise decision {cleaned_id!r} was not found."
                )
            )

        return decision

    def list_by_case(
        self,
        case_id: str,
    ) -> tuple[EnterpriseDecisionEngineResult, ...]:
        """Return all decisions for one case."""

        cleaned_case_id = str(case_id or "").strip()

        if not cleaned_case_id:
            raise ValueError("Enterprise decision case ID is required.")

        with self._lock:
            decision_ids = tuple(
                self._case_index.get(cleaned_case_id, ())
            )
            return tuple(
                self._decisions[decision_id]
                for decision_id in decision_ids
            )

    def list_decisions(
        self,
    ) -> tuple[EnterpriseDecisionEngineResult, ...]:
        """Return all decisions in deterministic order."""

        with self._lock:
            return tuple(
                self._decisions[key]
                for key in sorted(self._decisions)
            )

    def contains(
        self,
        decision_id: str,
    ) -> bool:
        """Return whether a decision exists."""

        cleaned_id = str(decision_id or "").strip()

        with self._lock:
            return cleaned_id in self._decisions

    def delete(
        self,
        decision_id: str,
    ) -> EnterpriseDecisionEngineResult:
        """Delete and return one decision."""

        cleaned_id = str(decision_id or "").strip()

        if not cleaned_id:
            raise ValueError("Enterprise decision ID is required.")

        with self._lock:
            decision = self._decisions.pop(cleaned_id, None)

            if decision is not None:
                case_decisions = self._case_index.get(
                    decision.case_id,
                    [],
                )
                self._case_index[decision.case_id] = [
                    item
                    for item in case_decisions
                    if item != cleaned_id
                ]

                if not self._case_index[decision.case_id]:
                    self._case_index.pop(decision.case_id, None)

        if decision is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise decision {cleaned_id!r} was not found."
                )
            )

        return decision

    def clear(self) -> None:
        """Remove all persisted decisions."""

        with self._lock:
            self._decisions.clear()
            self._case_index.clear()


_default_enterprise_decision_store = EnterpriseDecisionStore()


def get_enterprise_decision_store() -> EnterpriseDecisionStore:
    """Return the process-local default decision store."""

    return _default_enterprise_decision_store