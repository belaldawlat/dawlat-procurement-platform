"""Enterprise event bus with routing, persistence, retry and replay."""

from __future__ import annotations

from dataclasses import replace
import json

from app.orchestration.enterprise_event_models import (
    EnterpriseEvent,
    EnterpriseEventStatus,
)
from app.orchestration.enterprise_event_policy import EnterpriseEventPolicy
from app.orchestration.enterprise_event_registry import EnterpriseEventRegistry
from app.orchestration.enterprise_event_result import (
    EnterpriseEventBusResult,
    EnterpriseEventDelivery,
)
from app.orchestration.enterprise_event_router import EnterpriseEventRouter
from app.orchestration.enterprise_event_store import EnterpriseEventStore


class EnterpriseEventBus:
    def __init__(
        self,
        *,
        policy: EnterpriseEventPolicy | None = None,
        registry: EnterpriseEventRegistry | None = None,
        store: EnterpriseEventStore | None = None,
        router: EnterpriseEventRouter | None = None,
    ) -> None:
        self._policy = policy or EnterpriseEventPolicy(
            policy_id="default-enterprise-event",
            name="Default Enterprise Event Policy",
        )
        self._registry = registry or EnterpriseEventRegistry()
        self._store = store or EnterpriseEventStore()
        self._router = router or EnterpriseEventRouter(self._registry)

    @property
    def policy(self) -> EnterpriseEventPolicy:
        return self._policy

    @property
    def registry(self) -> EnterpriseEventRegistry:
        return self._registry

    @property
    def store(self) -> EnterpriseEventStore:
        return self._store

    @property
    def router(self) -> EnterpriseEventRouter:
        return self._router

    def publish(self, event: EnterpriseEvent) -> EnterpriseEventBusResult:
        if not self._policy.enabled:
            raise ValueError("Enterprise event policy is disabled.")

        if (
            self._policy.require_correlation_id
            and not event.correlation_id
        ):
            raise ValueError("Correlation ID is required by policy.")

        encoded = json.dumps(
            event.as_dict(),
            sort_keys=True,
            default=str,
        ).encode("utf-8")

        if len(encoded) > self._policy.maximum_event_size_bytes:
            raise ValueError("Enterprise event exceeds maximum size.")

        working_event = replace(
            event,
            status=EnterpriseEventStatus.PUBLISHED,
            maximum_attempts=self._policy.maximum_delivery_attempts,
        )

        if self._policy.persist_before_delivery:
            self._store.append(working_event)

        deliveries: list[EnterpriseEventDelivery] = []
        dead_lettered = False

        routes = self._router.route(working_event)

        if not routes:
            delivered_event = replace(
                working_event,
                status=EnterpriseEventStatus.DELIVERED,
            )
            if self._policy.persist_before_delivery:
                self._store.save(delivered_event)

            return EnterpriseEventBusResult(
                event=delivered_event,
                deliveries=(),
                dead_lettered=False,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata={"subscription_count": 0},
            )

        event_for_store = working_event

        for subscription_id, handler in routes:
            successful = False
            error = ""
            attempts = 0

            while attempts < self._policy.maximum_delivery_attempts:
                attempts += 1

                try:
                    handler(working_event.as_dict())
                    successful = True
                    break
                except Exception as exc:
                    error = str(exc)

            deliveries.append(
                EnterpriseEventDelivery(
                    event_id=working_event.event_id,
                    subscription_id=subscription_id,
                    successful=successful,
                    attempts=attempts,
                    error=error,
                )
            )

            if not successful:
                dead_lettered = (
                    self._policy.dead_letter_on_exhaustion
                )

        if dead_lettered:
            event_for_store = replace(
                working_event,
                status=EnterpriseEventStatus.DEAD_LETTERED,
                attempts=self._policy.maximum_delivery_attempts,
            )
            self._store.add_dead_letter(event_for_store)
        elif all(delivery.successful for delivery in deliveries):
            event_for_store = replace(
                working_event,
                status=EnterpriseEventStatus.DELIVERED,
            )
        else:
            event_for_store = replace(
                working_event,
                status=EnterpriseEventStatus.FAILED,
            )

        if self._policy.persist_before_delivery:
            self._store.save(event_for_store)
        else:
            self._store.append(event_for_store)

        return EnterpriseEventBusResult(
            event=event_for_store,
            deliveries=tuple(deliveries),
            dead_lettered=dead_lettered,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={"subscription_count": len(routes)},
        )

    def replay(self, event_id: str) -> EnterpriseEventBusResult:
        if not self._policy.allow_replay:
            raise ValueError("Enterprise event replay is disabled.")

        existing = self._store.get(event_id)
        replay_event = replace(
            existing,
            event_id=f"{existing.event_id}-replay",
            status=EnterpriseEventStatus.REPLAYED,
            attempts=0,
            causation_id=existing.event_id,
        )
        return self.publish(replay_event)


_default_enterprise_event_bus = EnterpriseEventBus()


def get_enterprise_event_bus() -> EnterpriseEventBus:
    return _default_enterprise_event_bus