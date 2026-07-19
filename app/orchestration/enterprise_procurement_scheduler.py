"""Global enterprise procurement scheduler and dispatcher."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from app.orchestration.enterprise_scheduler_models import (
    SchedulerResource,
    SchedulerTask,
    SchedulerTaskStatus,
)
from app.orchestration.enterprise_scheduler_policy import EnterpriseSchedulerPolicy
from app.orchestration.enterprise_scheduler_registry import EnterpriseSchedulerRegistry
from app.orchestration.enterprise_scheduler_result import (
    DispatchAssignment,
    EnterpriseSchedulerResult,
)
from app.orchestration.enterprise_task_queue import EnterpriseTaskQueue


class EnterpriseProcurementScheduler:
    """Prioritise, allocate and dispatch procurement work."""

    def __init__(
        self,
        *,
        policy: EnterpriseSchedulerPolicy | None = None,
        queue: EnterpriseTaskQueue | None = None,
        registry: EnterpriseSchedulerRegistry | None = None,
    ) -> None:
        self._policy = policy or EnterpriseSchedulerPolicy(
            policy_id="default-enterprise-scheduler",
            name="Default Enterprise Scheduler Policy",
        )
        self._queue = queue or EnterpriseTaskQueue(
            maximum_size=self._policy.maximum_queue_size
        )
        self._registry = registry or EnterpriseSchedulerRegistry()

    @property
    def policy(self) -> EnterpriseSchedulerPolicy:
        return self._policy

    @property
    def queue(self) -> EnterpriseTaskQueue:
        return self._queue

    @property
    def registry(self) -> EnterpriseSchedulerRegistry:
        return self._registry

    def submit(self, task: SchedulerTask) -> SchedulerTask:
        if not self._policy.enabled:
            raise ValueError("Enterprise scheduler policy is disabled.")
        return self._queue.enqueue(task)

    def dispatch(
        self,
        *,
        batch_size: int | None = None,
        now: datetime | None = None,
    ) -> EnterpriseSchedulerResult:
        if not self._policy.enabled:
            raise ValueError("Enterprise scheduler policy is disabled.")

        effective_batch_size = (
            batch_size
            if batch_size is not None
            else self._policy.maximum_dispatch_batch_size
        )
        if effective_batch_size < 1:
            raise ValueError("Dispatch batch size must be at least 1.")

        effective_batch_size = min(
            effective_batch_size,
            self._policy.maximum_dispatch_batch_size,
        )
        current_time = now or datetime.now(timezone.utc)

        queued_tasks = tuple(
            task
            for task in self._queue.list_tasks()
            if task.status is SchedulerTaskStatus.QUEUED
        )
        ordered_tasks = tuple(
            sorted(
                queued_tasks,
                key=lambda task: (
                    -self._scheduling_score(task, current_time),
                    task.created_at,
                    task.task_id,
                ),
            )
        )

        resource_states = {
            resource.resource_id: resource
            for resource in self._registry.list_resources()
            if resource.enabled
        }

        dispatched: list[SchedulerTask] = []
        pending: list[SchedulerTask] = []
        blocked: list[SchedulerTask] = []
        assignments: list[DispatchAssignment] = []

        for queue_position, task in enumerate(ordered_tasks, start=1):
            if len(dispatched) >= effective_batch_size:
                pending.append(task)
                continue

            resource = self._select_resource(
                task,
                tuple(resource_states.values()),
            )

            if resource is None:
                if self._policy.fail_closed_without_resource:
                    blocked_task = replace(
                        task,
                        status=SchedulerTaskStatus.BLOCKED,
                    )
                    self._queue.save(blocked_task)
                    blocked.append(blocked_task)
                else:
                    pending.append(task)
                continue

            dispatched_task = replace(
                task,
                status=SchedulerTaskStatus.DISPATCHED,
            )
            self._queue.save(dispatched_task)
            dispatched.append(dispatched_task)

            updated_resource = replace(
                resource,
                active_load=(
                    resource.active_load
                    + task.required_capacity
                ),
            )
            resource_states[resource.resource_id] = updated_resource
            self._registry.register(
                updated_resource,
                replace_existing=True,
            )

            assignments.append(
                DispatchAssignment(
                    task_id=task.task_id,
                    resource_id=resource.resource_id,
                    queue_position=queue_position,
                    scheduling_score=self._scheduling_score(
                        task,
                        current_time,
                    ),
                )
            )

        dispatched_ids = {task.task_id for task in dispatched}
        blocked_ids = {task.task_id for task in blocked}

        for task in ordered_tasks:
            if (
                task.task_id not in dispatched_ids
                and task.task_id not in blocked_ids
                and task not in pending
            ):
                pending.append(task)

        return EnterpriseSchedulerResult(
            dispatched_tasks=tuple(dispatched),
            pending_tasks=tuple(pending),
            blocked_tasks=tuple(blocked),
            assignments=tuple(assignments),
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "batch_size": effective_batch_size,
                "queue_size": len(queued_tasks),
                "resource_count": len(resource_states),
            },
        )

    def _select_resource(
        self,
        task: SchedulerTask,
        resources: tuple[SchedulerResource, ...],
    ) -> SchedulerResource | None:
        eligible = []

        for resource in resources:
            if task.task_type not in resource.supported_task_types:
                continue
            if resource.available_capacity < task.required_capacity:
                continue

            projected_utilisation = (
                (
                    resource.active_load
                    + task.required_capacity
                )
                / resource.capacity
                * 100.0
            )
            if (
                projected_utilisation
                > self._policy.maximum_resource_utilisation
            ):
                continue

            eligible.append(resource)

        if not eligible:
            return None

        return min(
            eligible,
            key=lambda resource: (
                resource.utilisation_rate,
                -resource.available_capacity,
                resource.resource_id,
            ),
        )

    def _scheduling_score(
        self,
        task: SchedulerTask,
        now: datetime,
    ) -> float:
        score = float(
            self._policy.priority_weight(task.priority)
        )

        if task.deadline_at:
            try:
                deadline = datetime.fromisoformat(
                    task.deadline_at.replace("Z", "+00:00")
                )
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)

                minutes_remaining = (
                    deadline - now
                ).total_seconds() / 60.0

                if minutes_remaining <= 0:
                    score += 2_000.0
                elif (
                    minutes_remaining
                    <= self._policy.deadline_boost_window_minutes
                ):
                    score += (
                        self._policy.deadline_boost_window_minutes
                        - minutes_remaining
                    )
            except ValueError:
                score -= 100.0

        score -= float(task.attempts * 10)
        score -= float(task.estimated_duration_seconds) / 10_000.0

        return round(score, 4)


_default_enterprise_procurement_scheduler = EnterpriseProcurementScheduler()


def get_enterprise_procurement_scheduler(
) -> EnterpriseProcurementScheduler:
    return _default_enterprise_procurement_scheduler