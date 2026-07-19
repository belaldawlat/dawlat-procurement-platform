"""Thread-safe priority queue for enterprise procurement tasks."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_scheduler_models import SchedulerTask
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError


class EnterpriseTaskQueue:
    def __init__(self, maximum_size: int = 10_000) -> None:
        if maximum_size < 1:
            raise ValueError("Queue maximum size must be at least 1.")

        self._maximum_size = maximum_size
        self._tasks: dict[str, SchedulerTask] = {}
        self._lock = threading.RLock()

    @property
    def maximum_size(self) -> int:
        return self._maximum_size

    def enqueue(self, task: SchedulerTask) -> SchedulerTask:
        if not isinstance(task, SchedulerTask):
            raise TypeError("Queue requires a SchedulerTask.")

        with self._lock:
            if task.task_id in self._tasks:
                raise WorkflowIntegrityError(
                    technical_message=f"Scheduler task {task.task_id!r} already exists."
                )
            if len(self._tasks) >= self._maximum_size:
                raise WorkflowIntegrityError(
                    technical_message="Scheduler queue capacity exceeded."
                )
            self._tasks[task.task_id] = task

        return task

    def get(self, task_id: str) -> SchedulerTask:
        cleaned_id = str(task_id or "").strip()
        if not cleaned_id:
            raise ValueError("Scheduler task ID is required.")

        with self._lock:
            task = self._tasks.get(cleaned_id)

        if task is None:
            raise WorkflowNotFoundError(
                technical_message=f"Scheduler task {cleaned_id!r} was not found."
            )
        return task

    def save(self, task: SchedulerTask) -> SchedulerTask:
        if not isinstance(task, SchedulerTask):
            raise TypeError("Queue requires a SchedulerTask.")

        with self._lock:
            if task.task_id not in self._tasks:
                raise WorkflowNotFoundError(
                    technical_message=f"Scheduler task {task.task_id!r} was not found."
                )
            self._tasks[task.task_id] = task

        return task

    def remove(self, task_id: str) -> SchedulerTask:
        cleaned_id = str(task_id or "").strip()

        with self._lock:
            task = self._tasks.pop(cleaned_id, None)

        if task is None:
            raise WorkflowNotFoundError(
                technical_message=f"Scheduler task {cleaned_id!r} was not found."
            )
        return task

    def list_tasks(self) -> tuple[SchedulerTask, ...]:
        with self._lock:
            return tuple(self._tasks[key] for key in sorted(self._tasks))

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()


_default_enterprise_task_queue = EnterpriseTaskQueue()


def get_enterprise_task_queue() -> EnterpriseTaskQueue:
    return _default_enterprise_task_queue