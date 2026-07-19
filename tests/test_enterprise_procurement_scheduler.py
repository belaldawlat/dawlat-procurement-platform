"""Tests for Phase 21 Package M enterprise procurement scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.orchestration import (
    EnterpriseProcurementScheduler,
    EnterpriseSchedulerPolicy,
    EnterpriseSchedulerRegistry,
    EnterpriseTaskQueue,
    SchedulerPriority,
    SchedulerResource,
    SchedulerTask,
    SchedulerTaskStatus,
    SchedulerTaskType,
    WorkflowIntegrityError,
)


def build_scheduler() -> EnterpriseProcurementScheduler:
    queue = EnterpriseTaskQueue(maximum_size=100)
    registry = EnterpriseSchedulerRegistry()
    registry.register(
        SchedulerResource(
            resource_id="worker-a",
            name="Worker A",
            capacity=5,
            supported_task_types=(
                SchedulerTaskType.PROCUREMENT,
                SchedulerTaskType.APPROVAL,
                SchedulerTaskType.SHIPMENT,
            ),
        )
    )

    return EnterpriseProcurementScheduler(
        policy=EnterpriseSchedulerPolicy(
            policy_id="scheduler",
            name="Scheduler",
            maximum_dispatch_batch_size=10,
            maximum_resource_utilisation=100,
        ),
        queue=queue,
        registry=registry,
    )


def task(
    entity_id: str,
    *,
    priority: SchedulerPriority = SchedulerPriority.NORMAL,
    task_type: SchedulerTaskType = SchedulerTaskType.PROCUREMENT,
    required_capacity: int = 1,
    deadline_at: str = "",
) -> SchedulerTask:
    return SchedulerTask(
        entity_id=entity_id,
        task_type=task_type,
        priority=priority,
        required_capacity=required_capacity,
        deadline_at=deadline_at,
    )


def test_policy_validates_utilisation() -> None:
    with pytest.raises(ValueError):
        EnterpriseSchedulerPolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_resource_utilisation=0,
        )


def test_queue_rejects_duplicate_task() -> None:
    queue = EnterpriseTaskQueue(maximum_size=10)
    item = task("PROC-1")
    queue.enqueue(item)

    with pytest.raises(WorkflowIntegrityError):
        queue.enqueue(item)


def test_scheduler_dispatches_supported_task() -> None:
    scheduler = build_scheduler()
    submitted = scheduler.submit(task("PROC-1"))

    result = scheduler.dispatch()

    assert result.dispatched_count == 1
    assert result.dispatched_tasks[0].task_id == submitted.task_id
    assert (
        result.dispatched_tasks[0].status
        is SchedulerTaskStatus.DISPATCHED
    )


def test_critical_task_is_dispatched_first() -> None:
    scheduler = build_scheduler()
    scheduler.submit(
        task(
            "PROC-NORMAL",
            priority=SchedulerPriority.NORMAL,
        )
    )
    critical = scheduler.submit(
        task(
            "PROC-CRITICAL",
            priority=SchedulerPriority.CRITICAL,
        )
    )

    result = scheduler.dispatch(batch_size=1)

    assert result.dispatched_tasks[0].task_id == critical.task_id
    assert result.pending_count == 1


def test_deadline_boosts_task_priority() -> None:
    scheduler = build_scheduler()
    now = datetime.now(timezone.utc)

    scheduler.submit(task("PROC-LATER"))
    urgent = scheduler.submit(
        task(
            "PROC-URGENT",
            deadline_at=(
                now + timedelta(minutes=5)
            ).isoformat(),
        )
    )

    result = scheduler.dispatch(
        batch_size=1,
        now=now,
    )

    assert result.dispatched_tasks[0].task_id == urgent.task_id


def test_unsupported_task_is_blocked() -> None:
    scheduler = build_scheduler()
    scheduler.submit(
        task(
            "RISK-1",
            task_type=SchedulerTaskType.RISK_REVIEW,
        )
    )

    result = scheduler.dispatch()

    assert result.blocked_count == 1
    assert (
        result.blocked_tasks[0].status
        is SchedulerTaskStatus.BLOCKED
    )


def test_capacity_limits_dispatch() -> None:
    scheduler = build_scheduler()
    scheduler.submit(
        task("PROC-1", required_capacity=4)
    )
    scheduler.submit(
        task("PROC-2", required_capacity=4)
    )

    result = scheduler.dispatch()

    assert result.dispatched_count == 1
    assert result.blocked_count == 1


def test_least_utilised_resource_is_selected() -> None:
    queue = EnterpriseTaskQueue(maximum_size=10)
    registry = EnterpriseSchedulerRegistry()
    registry.register(
        SchedulerResource(
            resource_id="busy",
            name="Busy",
            capacity=10,
            active_load=8,
            supported_task_types=(
                SchedulerTaskType.PROCUREMENT,
            ),
        )
    )
    registry.register(
        SchedulerResource(
            resource_id="free",
            name="Free",
            capacity=10,
            active_load=1,
            supported_task_types=(
                SchedulerTaskType.PROCUREMENT,
            ),
        )
    )
    scheduler = EnterpriseProcurementScheduler(
        policy=EnterpriseSchedulerPolicy(
            policy_id="scheduler",
            name="Scheduler",
            maximum_resource_utilisation=100,
        ),
        queue=queue,
        registry=registry,
    )
    scheduler.submit(task("PROC-1"))

    result = scheduler.dispatch()

    assert result.assignments[0].resource_id == "free"


def test_batch_size_limits_dispatch() -> None:
    scheduler = build_scheduler()

    for index in range(3):
        scheduler.submit(task(f"PROC-{index}"))

    result = scheduler.dispatch(batch_size=2)

    assert result.dispatched_count == 2
    assert result.pending_count == 1


def test_resource_load_is_updated() -> None:
    scheduler = build_scheduler()
    scheduler.submit(task("PROC-1", required_capacity=2))
    scheduler.dispatch()

    resource = scheduler.registry.get("worker-a")

    assert resource.active_load == 2
    assert resource.available_capacity == 3


def test_queue_capacity_is_enforced() -> None:
    queue = EnterpriseTaskQueue(maximum_size=1)
    queue.enqueue(task("PROC-1"))

    with pytest.raises(WorkflowIntegrityError):
        queue.enqueue(task("PROC-2"))


def test_disabled_policy_rejects_submission() -> None:
    scheduler = EnterpriseProcurementScheduler(
        policy=EnterpriseSchedulerPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        scheduler.submit(task("PROC-1"))


def test_result_serialises() -> None:
    scheduler = build_scheduler()
    scheduler.submit(task("PROC-1"))

    payload = scheduler.dispatch().as_dict()

    assert payload["dispatched_count"] == 1
    assert payload["assignments"]
    assert payload["dispatched_tasks"]


def test_task_serialises_safely() -> None:
    item = task("PROC-1")
    payload = item.as_dict()

    assert payload["entity_id"] == "PROC-1"
    assert payload["task_type"] == "procurement"
    assert payload["status"] == "queued"


def test_resource_validates_capacity() -> None:
    with pytest.raises(ValueError):
        SchedulerResource(
            resource_id="invalid",
            name="Invalid",
            capacity=1,
            active_load=2,
            supported_task_types=(
                SchedulerTaskType.PROCUREMENT,
            ),
        )