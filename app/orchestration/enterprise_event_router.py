"""Deterministic enterprise event routing."""

from __future__ import annotations

from app.orchestration.enterprise_event_models import EnterpriseEvent
from app.orchestration.enterprise_event_registry import (
    EnterpriseEventHandler,
    EnterpriseEventRegistry,
)


class EnterpriseEventRouter:
    def __init__(
        self,
        registry: EnterpriseEventRegistry | None = None,
    ) -> None:
        self._registry = registry or EnterpriseEventRegistry()

    @property
    def registry(self) -> EnterpriseEventRegistry:
        return self._registry

    def route(
        self,
        event: EnterpriseEvent,
    ) -> tuple[tuple[str, EnterpriseEventHandler], ...]:
        matches: list[tuple[str, EnterpriseEventHandler]] = []

        for subscription, handler in self._registry.list_subscriptions():
            if not subscription.enabled:
                continue
            if (
                subscription.event_type != "*"
                and subscription.event_type != event.event_type
            ):
                continue
            if (
                subscription.topic != "*"
                and subscription.topic != event.topic
            ):
                continue

            matches.append((subscription.subscription_id, handler))

        return tuple(sorted(matches, key=lambda item: item[0]))