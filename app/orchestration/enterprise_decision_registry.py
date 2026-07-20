"""Thread-safe registry for Package T decision evaluators."""

from __future__ import annotations

import threading
from typing import Callable

from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionContext,
)
from app.orchestration.enterprise_decision_result import (
    EnterpriseDecisionEngineResult,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


EnterpriseDecisionEvaluator = Callable[
    [EnterpriseDecisionContext],
    EnterpriseDecisionEngineResult,
]

# Backward-compatible alias retained for Package Q integrations.
EnterpriseDecisionStrategy = EnterpriseDecisionEvaluator


class EnterpriseDecisionRegistry:
    """Register named enterprise decision evaluators."""

    def __init__(self) -> None:
        self._evaluators: dict[str, EnterpriseDecisionEvaluator] = {}
        self._lock = threading.RLock()

    def register(
        self,
        evaluator_id: str,
        evaluator: EnterpriseDecisionEvaluator,
        *,
        replace_existing: bool = False,
    ) -> None:
        """Register a decision evaluator."""

        cleaned_id = str(evaluator_id or "").strip()

        if not cleaned_id:
            raise ValueError(
                "Enterprise decision evaluator ID is required."
            )
        if not callable(evaluator):
            raise TypeError(
                "Enterprise decision evaluator must be callable."
            )

        with self._lock:
            if (
                cleaned_id in self._evaluators
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Enterprise decision evaluator "
                        f"{cleaned_id!r} already exists."
                    )
                )

            self._evaluators[cleaned_id] = evaluator

    def get(
        self,
        evaluator_id: str,
    ) -> EnterpriseDecisionEvaluator:
        """Return one registered evaluator."""

        cleaned_id = str(evaluator_id or "").strip()

        if not cleaned_id:
            raise ValueError(
                "Enterprise decision evaluator ID is required."
            )

        with self._lock:
            evaluator = self._evaluators.get(cleaned_id)

        if evaluator is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise decision evaluator "
                    f"{cleaned_id!r} was not found."
                )
            )

        return evaluator

    def contains(
        self,
        evaluator_id: str,
    ) -> bool:
        """Return whether an evaluator exists."""

        cleaned_id = str(evaluator_id or "").strip()

        with self._lock:
            return cleaned_id in self._evaluators

    def list_evaluator_ids(self) -> tuple[str, ...]:
        """Return evaluator IDs in deterministic order."""

        with self._lock:
            return tuple(sorted(self._evaluators))

    def clear(self) -> None:
        """Remove every evaluator."""

        with self._lock:
            self._evaluators.clear()


_default_enterprise_decision_registry = EnterpriseDecisionRegistry()


def get_enterprise_decision_registry(
) -> EnterpriseDecisionRegistry:
    """Return the process-local default evaluator registry."""

    return _default_enterprise_decision_registry