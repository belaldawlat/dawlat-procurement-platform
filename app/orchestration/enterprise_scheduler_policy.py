"""Policy configuration for the enterprise procurement scheduler."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.enterprise_scheduler_models import SchedulerPriority


@dataclass(frozen=True)
class EnterpriseSchedulerPolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_queue_size: int = 10_000
    maximum_dispatch_batch_size: int = 100
    maximum_resource_utilisation: float = 90.0
    default_maximum_attempts: int = 3
    critical_priority_boost: int = 1_000
    high_priority_boost: int = 500
    normal_priority_boost: int = 100
    low_priority_boost: int = 0
    deadline_boost_window_minutes: int = 60
    fail_closed_without_resource: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Enterprise scheduler policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise scheduler policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Enterprise scheduler policy version is required.")
        if self.maximum_queue_size < 1:
            raise ValueError("Maximum queue size must be at least 1.")
        if self.maximum_dispatch_batch_size < 1:
            raise ValueError("Maximum dispatch batch size must be at least 1.")
        if not 0 < self.maximum_resource_utilisation <= 100:
            raise ValueError("Maximum resource utilisation must be greater than 0 and no more than 100.")
        if self.default_maximum_attempts < 1:
            raise ValueError("Default maximum attempts must be at least 1.")
        if self.deadline_boost_window_minutes < 0:
            raise ValueError("Deadline boost window cannot be negative.")

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())

    def priority_weight(self, priority: SchedulerPriority) -> int:
        return {
            SchedulerPriority.CRITICAL: self.critical_priority_boost,
            SchedulerPriority.HIGH: self.high_priority_boost,
            SchedulerPriority.NORMAL: self.normal_priority_boost,
            SchedulerPriority.LOW: self.low_priority_boost,
        }[priority]