"""Thread-safe registry for enterprise scheduler resources."""

from __future__ import annotations

import threading

from app.orchestration.enterprise_scheduler_models import SchedulerResource
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError


class EnterpriseSchedulerRegistry:
    def __init__(self) -> None:
        self._resources: dict[str, SchedulerResource] = {}
        self._lock = threading.RLock()

    def register(
        self,
        resource: SchedulerResource,
        *,
        replace_existing: bool = False,
    ) -> SchedulerResource:
        if not isinstance(resource, SchedulerResource):
            raise TypeError("Registry requires a SchedulerResource.")

        with self._lock:
            if resource.resource_id in self._resources and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Scheduler resource {resource.resource_id!r} already exists."
                    )
                )
            self._resources[resource.resource_id] = resource

        return resource

    def get(self, resource_id: str) -> SchedulerResource:
        cleaned_id = str(resource_id or "").strip()
        if not cleaned_id:
            raise ValueError("Scheduler resource ID is required.")

        with self._lock:
            resource = self._resources.get(cleaned_id)

        if resource is None:
            raise WorkflowNotFoundError(
                technical_message=f"Scheduler resource {cleaned_id!r} was not found."
            )
        return resource

    def list_resources(self) -> tuple[SchedulerResource, ...]:
        with self._lock:
            return tuple(self._resources[key] for key in sorted(self._resources))

    def clear(self) -> None:
        with self._lock:
            self._resources.clear()


_default_enterprise_scheduler_registry = EnterpriseSchedulerRegistry()


def get_enterprise_scheduler_registry() -> EnterpriseSchedulerRegistry:
    return _default_enterprise_scheduler_registry