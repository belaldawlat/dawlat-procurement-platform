"""Thread-safe registry for enterprise knowledge resolvers."""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.orchestration.enterprise_knowledge_models import (
    KnowledgeEntityType,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


KnowledgeResolver = Callable[[str], dict[str, Any]]


class EnterpriseKnowledgeRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[KnowledgeEntityType, KnowledgeResolver] = {}
        self._lock = threading.RLock()

    def register(
        self,
        entity_type: KnowledgeEntityType,
        resolver: KnowledgeResolver,
        *,
        replace_existing: bool = False,
    ) -> None:
        if not isinstance(entity_type, KnowledgeEntityType):
            raise TypeError("Entity type must be a KnowledgeEntityType.")
        if not callable(resolver):
            raise TypeError("Knowledge resolver must be callable.")

        with self._lock:
            if entity_type in self._resolvers and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Resolver for {entity_type.value!r} already exists."
                    )
                )
            self._resolvers[entity_type] = resolver

    def get(
        self,
        entity_type: KnowledgeEntityType,
    ) -> KnowledgeResolver:
        with self._lock:
            resolver = self._resolvers.get(entity_type)

        if resolver is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Resolver for {entity_type.value!r} was not found."
                )
            )

        return resolver

    def clear(self) -> None:
        with self._lock:
            self._resolvers.clear()


_default_enterprise_knowledge_registry = EnterpriseKnowledgeRegistry()


def get_enterprise_knowledge_registry(
) -> EnterpriseKnowledgeRegistry:
    return _default_enterprise_knowledge_registry