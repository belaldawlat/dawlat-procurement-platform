"""Thread-safe registry for enterprise decision strategies."""

from __future__ import annotations

import threading
from typing import Callable

from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionRequest,
)
from app.orchestration.enterprise_decision_result import (
    EnterpriseDecisionResult,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


EnterpriseDecisionStrategy = Callable[
    [EnterpriseDecisionRequest],
    EnterpriseDecisionResult,
]


class EnterpriseDecisionRegistry:
    """Thread-safe decision strategy registry."""

    def __init__(self) -> None:
        self._strategies: dict[
            str,
            EnterpriseDecisionStrategy,
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        strategy_id: str,
        strategy: EnterpriseDecisionStrategy,
        *,
        replace_existing: bool = False,
    ) -> None:
        cleaned_id = str(strategy_id or "").strip()

        if not cleaned_id:
            raise ValueError(
                "Enterprise decision strategy ID is required."
            )

        if not callable(strategy):
            raise TypeError(
                "Enterprise decision strategy must be callable."
            )

        with self._lock:
            if (
                cleaned_id in self._strategies
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Enterprise decision strategy "
                        f"{cleaned_id!r} already exists."
                    )
                )

            self._strategies[cleaned_id] = strategy

    def get(
        self,
        strategy_id: str,
    ) -> EnterpriseDecisionStrategy:
        cleaned_id = str(strategy_id or "").strip()

        if not cleaned_id:
            raise ValueError(
                "Enterprise decision strategy ID is required."
            )

        with self._lock:
            strategy = self._strategies.get(cleaned_id)

        if strategy is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise decision strategy "
                    f"{cleaned_id!r} was not found."
                )
            )

        return strategy

    def clear(self) -> None:
        with self._lock:
            self._strategies.clear()


_default_enterprise_decision_registry = EnterpriseDecisionRegistry()


def get_enterprise_decision_registry(
) -> EnterpriseDecisionRegistry:
    return _default_enterprise_decision_registry