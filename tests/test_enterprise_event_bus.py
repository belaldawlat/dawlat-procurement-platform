"""Tests for Phase 21 Package N enterprise event bus."""

from __future__ import annotations

import pytest

from app.orchestration import (
    EnterpriseEvent,
    EnterpriseEventBus,
    EnterpriseEventPolicy,
    EnterpriseEventPriority,
    EnterpriseEventRegistry,
    EnterpriseEventRouter,
    EnterpriseEventStatus,
    EnterpriseEventStore,
    EnterpriseEventSubscription,
    WorkflowIntegrityError,
)


def build_bus(
    *,
    maximum_attempts: int = 3,
) -> EnterpriseEventBus:
    registry = EnterpriseEventRegistry()
    store = EnterpriseEventStore()
    return EnterpriseEventBus(
        policy=EnterpriseEventPolicy(
            policy_id="event-policy",
            name="Event Policy",
            maximum_delivery_attempts=maximum_attempts,
        ),
        registry=registry,
        store=store,
        router=EnterpriseEventRouter(registry),
    )


def event(
    event_type: str = "procurement.created",
    *,
    topic: str = "procurement",
    correlation_id: str = "CORR-100",
) -> EnterpriseEvent:
    return EnterpriseEvent(
        event_type=event_type,
        aggregate_id="PROC-100",
        payload={"supplier": "SUP-100"},
        topic=topic,
        correlation_id=correlation_id,
        priority=EnterpriseEventPriority.HIGH,
    )


def test_policy_validates_attempts() -> None:
    with pytest.raises(ValueError):
        EnterpriseEventPolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_delivery_attempts=0,
        )


def test_event_validates_required_fields() -> None:
    with pytest.raises(ValueError):
        EnterpriseEvent(
            event_type="",
            aggregate_id="PROC-100",
            payload={},
        )


def test_registry_rejects_duplicate_subscription() -> None:
    registry = EnterpriseEventRegistry()
    subscription = EnterpriseEventSubscription(
        subscription_id="sub-1",
        event_type="procurement.created",
    )
    registry.register(subscription, lambda payload: payload)

    with pytest.raises(WorkflowIntegrityError):
        registry.register(subscription, lambda payload: payload)


def test_router_matches_event_type_and_topic() -> None:
    registry = EnterpriseEventRegistry()
    registry.register(
        EnterpriseEventSubscription(
            subscription_id="sub-1",
            event_type="procurement.created",
            topic="procurement",
        ),
        lambda payload: payload,
    )

    routes = EnterpriseEventRouter(registry).route(event())

    assert len(routes) == 1
    assert routes[0][0] == "sub-1"


def test_router_supports_wildcards() -> None:
    registry = EnterpriseEventRegistry()
    registry.register(
        EnterpriseEventSubscription(
            subscription_id="sub-all",
            event_type="*",
            topic="*",
        ),
        lambda payload: payload,
    )

    assert len(EnterpriseEventRouter(registry).route(event())) == 1


def test_publish_delivers_to_subscriber() -> None:
    bus = build_bus()
    received = []

    bus.registry.register(
        EnterpriseEventSubscription(
            subscription_id="sub-1",
            event_type="procurement.created",
            topic="procurement",
        ),
        lambda payload: received.append(payload),
    )

    result = bus.publish(event())

    assert result.delivered_count == 1
    assert result.failed_count == 0
    assert result.event.status is EnterpriseEventStatus.DELIVERED
    assert received[0]["aggregate_id"] == "PROC-100"


def test_publish_persists_event() -> None:
    bus = build_bus()
    item = event()

    result = bus.publish(item)
    stored = bus.store.get(item.event_id)

    assert stored.event_id == result.event.event_id
    assert stored.status is EnterpriseEventStatus.DELIVERED


def test_publish_without_subscribers_is_delivered() -> None:
    result = build_bus().publish(event())

    assert result.event.status is EnterpriseEventStatus.DELIVERED
    assert result.deliveries == ()


def test_failed_handler_retries_and_dead_letters() -> None:
    bus = build_bus(maximum_attempts=2)

    def failing_handler(payload):
        raise RuntimeError("delivery failed")

    bus.registry.register(
        EnterpriseEventSubscription(
            subscription_id="sub-fail",
            event_type="procurement.created",
            topic="procurement",
        ),
        failing_handler,
    )

    result = bus.publish(event())

    assert result.dead_lettered is True
    assert result.failed_count == 1
    assert result.deliveries[0].attempts == 2
    assert result.event.status is EnterpriseEventStatus.DEAD_LETTERED
    assert len(bus.store.list_dead_letters()) == 1


def test_transient_handler_succeeds_on_retry() -> None:
    bus = build_bus(maximum_attempts=3)
    state = {"count": 0}

    def transient_handler(payload):
        state["count"] += 1
        if state["count"] < 2:
            raise RuntimeError("temporary")

    bus.registry.register(
        EnterpriseEventSubscription(
            subscription_id="sub-retry",
            event_type="procurement.created",
            topic="procurement",
        ),
        transient_handler,
    )

    result = bus.publish(event())

    assert result.dead_lettered is False
    assert result.deliveries[0].successful is True
    assert result.deliveries[0].attempts == 2


def test_correlation_id_can_be_required() -> None:
    bus = EnterpriseEventBus(
        policy=EnterpriseEventPolicy(
            policy_id="strict",
            name="Strict",
            require_correlation_id=True,
        )
    )

    with pytest.raises(ValueError):
        bus.publish(event(correlation_id=""))


def test_event_size_is_enforced() -> None:
    bus = EnterpriseEventBus(
        policy=EnterpriseEventPolicy(
            policy_id="small",
            name="Small",
            maximum_event_size_bytes=10,
        )
    )

    with pytest.raises(ValueError):
        bus.publish(event())


def test_replay_creates_new_event() -> None:
    bus = build_bus()
    original = event()
    bus.publish(original)

    replay = bus.replay(original.event_id)

    assert replay.event.event_id.endswith("-replay")
    assert replay.event.causation_id == original.event_id
    assert len(bus.store.list_events()) == 2


def test_replay_can_be_disabled() -> None:
    store = EnterpriseEventStore()
    bus = EnterpriseEventBus(
        policy=EnterpriseEventPolicy(
            policy_id="no-replay",
            name="No Replay",
            allow_replay=False,
        ),
        store=store,
    )
    original = event()
    bus.publish(original)

    with pytest.raises(ValueError):
        bus.replay(original.event_id)


def test_result_serialises_safely() -> None:
    result = build_bus().publish(event())
    payload = result.as_dict()

    assert payload["event"]["event_type"] == "procurement.created"
    assert payload["delivered_count"] == 0
    assert payload["dead_lettered"] is False


def test_disabled_policy_rejects_publish() -> None:
    bus = EnterpriseEventBus(
        policy=EnterpriseEventPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        bus.publish(event())