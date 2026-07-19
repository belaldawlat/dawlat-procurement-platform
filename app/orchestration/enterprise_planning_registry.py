"""Thread-safe registry for enterprise planning strategies."""

from __future__ import annotations

import threading
from typing import Callable

from app.orchestration.enterprise_planning_models import EnterprisePlan
from app.orchestration.enterprise_planning_result import EnterprisePlanningResult
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


EnterprisePlanningStrategy = Callable[
    [EnterprisePlan],
    EnterprisePlanningResult,
]


class EnterprisePlanningRegistry:
    """Store named enterprise planning strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, EnterprisePlanningStrategy] = {}
        self._lock = threading.RLock()

    def register(
        self,
        strategy_id: str,
        strategy: EnterprisePlanningStrategy,
        *,
        replace_existing: bool = False,
    ) -> None:
        cleaned_id = str(strategy_id or "").strip()

        if not cleaned_id:
            raise ValueError(
                "Enterprise planning strategy ID is required."
            )
        if not callable(strategy):
            raise TypeError(
                "Enterprise planning strategy must be callable."
            )

        with self._lock:
            if (
                cleaned_id in self._strategies
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Enterprise planning strategy "
                        f"{cleaned_id!r} already exists."
                    )
                )

            self._strategies[cleaned_id] = strategy

    def get(
        self,
        strategy_id: str,
    ) -> EnterprisePlanningStrategy:
        cleaned_id = str(strategy_id or "").strip()

        if not cleaned_id:
            raise ValueError(
                "Enterprise planning strategy ID is required."
            )

        with self._lock:
            strategy = self._strategies.get(cleaned_id)

        if strategy is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Enterprise planning strategy "
                    f"{cleaned_id!r} was not found."
                )
            )

        return strategy

    def contains(self, strategy_id: str) -> bool:
        cleaned_id = str(strategy_id or "").strip()

        with self._lock:
            return cleaned_id in self._strategies

    def list_strategy_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._strategies))

    def clear(self) -> None:
        with self._lock:
            self._strategies.clear()


_default_enterprise_planning_registry = EnterprisePlanningRegistry()


def get_enterprise_planning_registry(
) -> EnterprisePlanningRegistry:
    return _default_enterprise_planning_registry