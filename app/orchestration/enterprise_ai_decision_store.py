"""Thread-safe decision history and replay store."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_ai_decision_result import (
    EnterpriseAIDecisionResult,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


class EnterpriseAIDecisionStore:
    def __init__(self) -> None:
        self._results: dict[str, EnterpriseAIDecisionResult] = {}
        self._lock = threading.RLock()

    def append(
        self,
        result: EnterpriseAIDecisionResult,
    ) -> EnterpriseAIDecisionResult:
        if not isinstance(result, EnterpriseAIDecisionResult):
            raise TypeError(
                "Decision store requires an EnterpriseAIDecisionResult."
            )

        with self._lock:
            if result.request_id in self._results:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"AI decision result {result.request_id!r} already exists."
                    )
                )
            self._results[result.request_id] = result

        return result

    def get(self, request_id: str) -> EnterpriseAIDecisionResult:
        cleaned = str(request_id or "").strip()
        if not cleaned:
            raise ValueError("AI decision request ID is required.")

        with self._lock:
            result = self._results.get(cleaned)

        if result is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"AI decision result {cleaned!r} was not found."
                )
            )

        return result

    def list_results(self) -> tuple[EnterpriseAIDecisionResult, ...]:
        with self._lock:
            return tuple(
                self._results[key]
                for key in sorted(self._results)
            )

    def clear(self) -> None:
        with self._lock:
            self._results.clear()


_default_enterprise_ai_decision_store = EnterpriseAIDecisionStore()


def get_enterprise_ai_decision_store() -> EnterpriseAIDecisionStore:
    return _default_enterprise_ai_decision_store