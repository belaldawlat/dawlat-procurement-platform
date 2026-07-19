"""Thread-safe subscription registry for enterprise events."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.enterprise_event_models import EnterpriseEventSubscription
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError


EnterpriseEventHandler = Callable[[dict[str, Any]], Any]


class EnterpriseEventRegistry:
    def __init__(self) -> None:
        self._subscriptions: dict[
            str,
            tuple[EnterpriseEventSubscription, EnterpriseEventHandler],
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        subscription: EnterpriseEventSubscription,
        handler: EnterpriseEventHandler,
        *,
        replace_existing: bool = False,
    ) -> EnterpriseEventSubscription:
        if not isinstance(subscription, EnterpriseEventSubscription):
            raise TypeError("Registry requires an EnterpriseEventSubscription.")
        if not callable(handler):
            raise TypeError("Enterprise event handler must be callable.")

        with self._lock:
            if (
                subscription.subscription_id in self._subscriptions
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Subscription {subscription.subscription_id!r} already exists."
                    )
                )
            self._subscriptions[subscription.subscription_id] = (
                subscription,
                handler,
            )

        return subscription

    def get(
        self,
        subscription_id: str,
    ) -> tuple[EnterpriseEventSubscription, EnterpriseEventHandler]:
        cleaned = str(subscription_id or "").strip()
        if not cleaned:
            raise ValueError("Subscription ID is required.")

        with self._lock:
            item = self._subscriptions.get(cleaned)

        if item is None:
            raise WorkflowNotFoundError(
                technical_message=f"Subscription {cleaned!r} was not found."
            )
        return item

    def list_subscriptions(
        self,
    ) -> tuple[
        tuple[EnterpriseEventSubscription, EnterpriseEventHandler],
        ...,
    ]:
        with self._lock:
            return tuple(
                self._subscriptions[key]
                for key in sorted(self._subscriptions)
            )

    def clear(self) -> None:
        with self._lock:
            self._subscriptions.clear()


_default_enterprise_event_registry = EnterpriseEventRegistry()


def get_enterprise_event_registry() -> EnterpriseEventRegistry:
    return _default_enterprise_event_registry