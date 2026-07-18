"""Enterprise event dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4


@dataclass(frozen=True)
class PlatformEvent:
    event_id: str
    event_name: str
    payload: dict[str, Any]
    correlation_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @classmethod
    def create(
        cls,
        *,
        event_name: str,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> "PlatformEvent":
        return cls(
            event_id=f"EVT-{uuid4().hex[:16].upper()}",
            event_name=event_name,
            payload=payload,
            correlation_id=correlation_id,
        )


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[
            str,
            list[Callable[[PlatformEvent], None]],
        ] = {}

    def subscribe(
        self,
        event_name: str,
        handler: Callable[[PlatformEvent], None],
    ) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def dispatch(self, event: PlatformEvent) -> int:
        handlers = self._handlers.get(event.event_name, [])
        for handler in handlers:
            handler(event)
        return len(handlers)


_dispatcher = EventDispatcher()


def get_event_dispatcher() -> EventDispatcher:
    return _dispatcher