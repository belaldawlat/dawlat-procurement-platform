"""Bounded institutional memory for autonomous procurement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    entity_type: str
    entity_id: str
    event_type: str
    summary: str
    outcome_score: int
    confidence_score: int
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class EnterpriseMemoryEngine:
    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def remember(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def recall(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        results = [
            record
            for record in self._records
            if (
                entity_type is None
                or record.entity_type == entity_type
            )
            and (
                entity_id is None
                or record.entity_id == entity_id
            )
            and (
                event_type is None
                or record.event_type == event_type
            )
        ]

        results.sort(
            key=lambda record: record.created_at,
            reverse=True,
        )
        return results[: max(1, min(limit, 1000))]

    def baseline(
        self,
        *,
        entity_type: str,
        entity_id: str,
    ) -> float | None:
        records = self.recall(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=1000,
        )

        if not records:
            return None

        return round(
            sum(record.outcome_score for record in records)
            / len(records),
            2,
        )


_engine = EnterpriseMemoryEngine()


def get_enterprise_memory_engine() -> EnterpriseMemoryEngine:
    return _engine