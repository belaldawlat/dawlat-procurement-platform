"""Thread-safe memory for enterprise AI agents."""

from __future__ import annotations

import threading
from typing import Any

from app.observability.redaction import redact_mapping


class EnterpriseAgentMemory:
    """Store safe agent memory by agent and key."""

    def __init__(self) -> None:
        self._memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def write(
        self,
        agent_id: str,
        key: str,
        value: Any,
    ) -> None:
        cleaned_agent_id = str(agent_id or "").strip()
        cleaned_key = str(key or "").strip()

        if not cleaned_agent_id:
            raise ValueError("Agent ID is required.")
        if not cleaned_key:
            raise ValueError("Memory key is required.")

        safe_value = (
            redact_mapping(value)
            if isinstance(value, dict)
            else value
        )

        with self._lock:
            self._memory.setdefault(cleaned_agent_id, {})[
                cleaned_key
            ] = safe_value

    def read(
        self,
        agent_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        cleaned_agent_id = str(agent_id or "").strip()
        cleaned_key = str(key or "").strip()

        with self._lock:
            return self._memory.get(
                cleaned_agent_id,
                {},
            ).get(cleaned_key, default)

    def snapshot(self, agent_id: str) -> dict[str, Any]:
        cleaned_agent_id = str(agent_id or "").strip()

        with self._lock:
            return dict(
                self._memory.get(cleaned_agent_id, {})
            )

    def clear(self, agent_id: str | None = None) -> None:
        with self._lock:
            if agent_id is None:
                self._memory.clear()
            else:
                self._memory.pop(
                    str(agent_id).strip(),
                    None,
                )


_default_enterprise_agent_memory = EnterpriseAgentMemory()


def get_enterprise_agent_memory() -> EnterpriseAgentMemory:
    return _default_enterprise_agent_memory