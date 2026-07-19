"""Thread-safe event and dead-letter persistence."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_event_models import EnterpriseEvent
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError


class EnterpriseEventStore:
    def __init__(self) -> None:
        self._events: dict[str, EnterpriseEvent] = {}
        self._dead_letters: dict[str, EnterpriseEvent] = {}
        self._lock = threading.RLock()

    def append(self, event: EnterpriseEvent) -> EnterpriseEvent:
        if not isinstance(event, EnterpriseEvent):
            raise TypeError("Event store requires an EnterpriseEvent.")

        with self._lock:
            if event.event_id in self._events:
                raise WorkflowIntegrityError(
                    technical_message=f"Enterprise event {event.event_id!r} already exists."
                )
            self._events[event.event_id] = event

        return event

    def save(self, event: EnterpriseEvent) -> EnterpriseEvent:
        with self._lock:
            if event.event_id not in self._events:
                raise WorkflowNotFoundError(
                    technical_message=f"Enterprise event {event.event_id!r} was not found."
                )
            self._events[event.event_id] = event
        return event

    def get(self, event_id: str) -> EnterpriseEvent:
        cleaned = str(event_id or "").strip()
        if not cleaned:
            raise ValueError("Enterprise event ID is required.")

        with self._lock:
            event = self._events.get(cleaned)

        if event is None:
            raise WorkflowNotFoundError(
                technical_message=f"Enterprise event {cleaned!r} was not found."
            )
        return event

    def list_events(self) -> tuple[EnterpriseEvent, ...]:
        with self._lock:
            return tuple(self._events[key] for key in sorted(self._events))

    def add_dead_letter(self, event: EnterpriseEvent) -> EnterpriseEvent:
        with self._lock:
            self._dead_letters[event.event_id] = event
        return event

    def list_dead_letters(self) -> tuple[EnterpriseEvent, ...]:
        with self._lock:
            return tuple(
                self._dead_letters[key]
                for key in sorted(self._dead_letters)
            )

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._dead_letters.clear()


_default_enterprise_event_store = EnterpriseEventStore()


def get_enterprise_event_store() -> EnterpriseEventStore:
    return _default_enterprise_event_store