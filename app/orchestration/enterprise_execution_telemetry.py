"""Execution telemetry for enterprise execution intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
import threading
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseExecutionTelemetryRecord:
    execution_id: str
    step_id: str
    metric_name: str
    metric_value: float
    unit: str
    telemetry_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    recorded_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.telemetry_id or "").strip():
            raise ValueError("Execution telemetry ID is required.")
        if not str(self.execution_id or "").strip():
            raise ValueError("Execution telemetry execution ID is required.")
        if not str(self.metric_name or "").strip():
            raise ValueError("Execution telemetry metric name is required.")
        if not str(self.unit or "").strip():
            raise ValueError("Execution telemetry unit is required.")

        object.__setattr__(self, "telemetry_id", str(self.telemetry_id).strip())
        object.__setattr__(self, "execution_id", str(self.execution_id).strip())
        object.__setattr__(self, "step_id", str(self.step_id or "").strip())
        object.__setattr__(self, "metric_name", str(self.metric_name).strip())
        object.__setattr__(self, "unit", str(self.unit).strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "telemetry_id": self.telemetry_id,
            "execution_id": self.execution_id,
            "step_id": self.step_id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "unit": self.unit,
            "recorded_at": self.recorded_at,
            "metadata": redact_mapping(self.metadata),
        }


class EnterpriseExecutionTelemetry:
    def __init__(self) -> None:
        self._records: list[EnterpriseExecutionTelemetryRecord] = []
        self._lock = threading.RLock()

    def record(
        self,
        *,
        execution_id: str,
        metric_name: str,
        metric_value: float,
        unit: str,
        step_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseExecutionTelemetryRecord:
        record = EnterpriseExecutionTelemetryRecord(
            execution_id=execution_id,
            step_id=step_id,
            metric_name=metric_name,
            metric_value=float(metric_value),
            unit=unit,
            metadata=metadata or {},
        )

        with self._lock:
            self._records.append(record)

        return record

    def list_records(
        self,
        *,
        execution_id: str | None = None,
        step_id: str | None = None,
    ) -> tuple[EnterpriseExecutionTelemetryRecord, ...]:
        cleaned_execution_id = (
            str(execution_id).strip()
            if execution_id is not None
            else None
        )
        cleaned_step_id = (
            str(step_id).strip()
            if step_id is not None
            else None
        )

        with self._lock:
            return tuple(
                record
                for record in self._records
                if (
                    cleaned_execution_id is None
                    or record.execution_id == cleaned_execution_id
                )
                and (
                    cleaned_step_id is None
                    or record.step_id == cleaned_step_id
                )
            )

    def aggregate(
        self,
        *,
        execution_id: str,
        metric_name: str,
    ) -> dict[str, float]:
        records = tuple(
            record
            for record in self.list_records(execution_id=execution_id)
            if record.metric_name == metric_name
        )

        if not records:
            return {
                "count": 0.0,
                "sum": 0.0,
                "average": 0.0,
                "minimum": 0.0,
                "maximum": 0.0,
            }

        values = [record.metric_value for record in records]

        return {
            "count": float(len(values)),
            "sum": round(sum(values), 6),
            "average": round(sum(values) / len(values), 6),
            "minimum": round(min(values), 6),
            "maximum": round(max(values), 6),
        }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


_default_enterprise_execution_telemetry = EnterpriseExecutionTelemetry()


def get_enterprise_execution_telemetry(
) -> EnterpriseExecutionTelemetry:
    return _default_enterprise_execution_telemetry