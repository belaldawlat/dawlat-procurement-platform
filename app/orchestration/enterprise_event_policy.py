"""Policy configuration for the enterprise event bus."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseEventPolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_event_size_bytes: int = 1_000_000
    maximum_delivery_attempts: int = 3
    persist_before_delivery: bool = True
    dead_letter_on_exhaustion: bool = True
    require_correlation_id: bool = False
    allow_replay: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Enterprise event policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise event policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Enterprise event policy version is required.")
        if self.maximum_event_size_bytes < 1:
            raise ValueError("Maximum event size must be at least 1 byte.")
        if self.maximum_delivery_attempts < 1:
            raise ValueError("Maximum delivery attempts must be at least 1.")

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())