"""Thread-safe strategy registry for the AI decision network."""

from __future__ import annotations

import threading
from typing import Callable

from app.orchestration.enterprise_ai_decision_models import AIDecisionRequest
from app.orchestration.enterprise_ai_decision_result import (
    EnterpriseAIDecisionResult,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


AIDecisionStrategy = Callable[
    [AIDecisionRequest],
    EnterpriseAIDecisionResult,
]


class EnterpriseAIDecisionRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, AIDecisionStrategy] = {}
        self._lock = threading.RLock()

    def register(
        self,
        strategy_id: str,
        strategy: AIDecisionStrategy,
        *,
        replace_existing: bool = False,
    ) -> None:
        cleaned = str(strategy_id or "").strip()
        if not cleaned:
            raise ValueError("AI decision strategy ID is required.")
        if not callable(strategy):
            raise TypeError("AI decision strategy must be callable.")

        with self._lock:
            if cleaned in self._strategies and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"AI decision strategy {cleaned!r} already exists."
                    )
                )
            self._strategies[cleaned] = strategy

    def get(self, strategy_id: str) -> AIDecisionStrategy:
        cleaned = str(strategy_id or "").strip()
        if not cleaned:
            raise ValueError("AI decision strategy ID is required.")

        with self._lock:
            strategy = self._strategies.get(cleaned)

        if strategy is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"AI decision strategy {cleaned!r} was not found."
                )
            )

        return strategy

    def clear(self) -> None:
        with self._lock:
            self._strategies.clear()


_default_enterprise_ai_decision_registry = EnterpriseAIDecisionRegistry()


def get_enterprise_ai_decision_registry(
) -> EnterpriseAIDecisionRegistry:
    return _default_enterprise_ai_decision_registry