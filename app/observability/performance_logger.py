"""Performance and execution timing instrumentation."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from app.observability.logging_config import get_logger


@dataclass(frozen=True)
class PerformanceMeasurement:
    """Immutable performance measurement."""

    operation: str
    duration_ms: float
    successful: bool
    warning_threshold_ms: float


class PerformanceLogger:
    """Measure and record operation performance."""

    def __init__(self) -> None:
        self._logger = get_logger("performance")

    @contextmanager
    def measure(
        self,
        operation: str,
        *,
        warning_threshold_ms: float = 1_000.0,
    ) -> Iterator[None]:
        """Measure an operation and record its duration."""

        started_at = time.perf_counter()
        successful = False

        try:
            yield
            successful = True
        except Exception:
            raise
        finally:
            duration_ms = (
                time.perf_counter() - started_at
            ) * 1_000.0

            measurement = PerformanceMeasurement(
                operation=str(operation or "unknown"),
                duration_ms=round(duration_ms, 3),
                successful=successful,
                warning_threshold_ms=warning_threshold_ms,
            )

            log_method = (
                self._logger.warning
                if duration_ms >= warning_threshold_ms
                else self._logger.info
            )

            log_method(
                "Operation performance measured.",
                extra={
                    "performance": measurement,
                    "operation": measurement.operation,
                    "duration_ms": measurement.duration_ms,
                    "successful": measurement.successful,
                },
            )


_performance_logger = PerformanceLogger()


def get_performance_logger() -> PerformanceLogger:
    """Return the shared performance logger."""

    return _performance_logger