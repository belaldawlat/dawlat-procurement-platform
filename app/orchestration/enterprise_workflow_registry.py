"""Registry for enterprise workflow templates and factories."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from threading import RLock
from typing import Any, Callable, Iterable

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_models import EnterpriseWorkflow
from app.orchestration.enterprise_workflow_template import (
    EnterpriseWorkflowTemplate,
)
from app.orchestration.enterprise_workflow_versioning import (
    EnterpriseWorkflowTemplateVersion,
    EnterpriseWorkflowVersioning,
    get_enterprise_workflow_versioning,
)


EnterpriseWorkflowFactory = Callable[
    [EnterpriseWorkflowTemplate, dict[str, Any]],
    EnterpriseWorkflow,
]


@dataclass(frozen=True)
class EnterpriseWorkflowRegistryEntry:
    """One registered workflow template and optional factory."""

    template_id: str
    version: str
    name: str
    category: str
    active: bool
    factory_name: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.template_id or "").strip():
            raise ValueError("Registry template ID is required.")
        if not str(self.version or "").strip():
            raise ValueError("Registry template version is required.")
        if not str(self.name or "").strip():
            raise ValueError("Registry template name is required.")

        object.__setattr__(
            self,
            "template_id",
            str(self.template_id).strip(),
        )
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(
            self,
            "category",
            str(self.category or "general").strip(),
        )
        object.__setattr__(
            self,
            "factory_name",
            str(self.factory_name or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @classmethod
    def from_template(
        cls,
        template: EnterpriseWorkflowTemplate,
        *,
        factory_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "EnterpriseWorkflowRegistryEntry":
        """Build a registry entry from a workflow template."""

        return cls(
            template_id=template.template_id,
            version=template.version,
            name=template.name,
            category=template.category,
            active=template.active,
            factory_name=factory_name,
            metadata=metadata or {},
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "template_id": self.template_id,
            "version": self.version,
            "name": self.name,
            "category": self.category,
            "active": self.active,
            "factory_name": self.factory_name,
            "metadata": redact_mapping(self.metadata),
        }


class EnterpriseWorkflowRegistry:
    """Thread-safe registry of versioned workflow templates."""

    def __init__(
        self,
        *,
        versioning: EnterpriseWorkflowVersioning | None = None,
    ) -> None:
        self._versioning = (
            versioning or get_enterprise_workflow_versioning()
        )
        self._entries: dict[
            tuple[str, str],
            EnterpriseWorkflowRegistryEntry,
        ] = {}
        self._factories: dict[
            tuple[str, str],
            EnterpriseWorkflowFactory,
        ] = {}
        self._lock = RLock()

    @property
    def versioning(self) -> EnterpriseWorkflowVersioning:
        """Return the backing version manager."""

        return self._versioning

    def register(
        self,
        template: EnterpriseWorkflowTemplate,
        *,
        created_by: str,
        change_summary: str = "Registered workflow template.",
        factory: EnterpriseWorkflowFactory | None = None,
        factory_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseWorkflowRegistryEntry:
        """Register a template and its initial version."""

        key = (template.template_id, template.version)

        with self._lock:
            if key in self._entries:
                raise ValueError(
                    "Workflow template version is already registered."
                )

            if not self._versioning.has_version(*key):
                self._versioning.register_initial(
                    template,
                    created_by=created_by,
                    change_summary=change_summary,
                    metadata=metadata,
                )

            entry = EnterpriseWorkflowRegistryEntry.from_template(
                template,
                factory_name=factory_name,
                metadata=metadata,
            )
            self._entries[key] = entry

            if factory is not None:
                self._factories[key] = factory

            return entry

    def register_version(
        self,
        record: EnterpriseWorkflowTemplateVersion,
        *,
        factory: EnterpriseWorkflowFactory | None = None,
        factory_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseWorkflowRegistryEntry:
        """Register an existing version record with the registry."""

        key = (
            record.template.template_id,
            str(record.version),
        )

        with self._lock:
            if key in self._entries:
                raise ValueError(
                    "Workflow template version is already registered."
                )

            if not self._versioning.has_version(*key):
                self._versioning.register_explicit(record)

            entry = EnterpriseWorkflowRegistryEntry.from_template(
                record.template,
                factory_name=factory_name,
                metadata=metadata,
            )
            self._entries[key] = entry

            if factory is not None:
                self._factories[key] = factory

            return entry

    def unregister(self, template_id: str, version: str) -> None:
        """Remove one template version from the runtime registry."""

        key = (
            str(template_id or "").strip(),
            str(version or "").strip(),
        )

        with self._lock:
            if key not in self._entries:
                raise KeyError(
                    "Workflow registry entry was not found."
                )

            self._entries.pop(key)
            self._factories.pop(key, None)

    def get_entry(
        self,
        template_id: str,
        version: str | None = None,
    ) -> EnterpriseWorkflowRegistryEntry:
        """Return an exact or latest registry entry."""

        cleaned_id = str(template_id or "").strip()

        with self._lock:
            if version is None:
                record = self._versioning.get_latest(cleaned_id)
                key = (cleaned_id, str(record.version))
            else:
                key = (cleaned_id, str(version).strip())

            try:
                return self._entries[key]
            except KeyError as exc:
                raise KeyError(
                    "Workflow registry entry was not found."
                ) from exc

    def get_template(
        self,
        template_id: str,
        version: str | None = None,
    ) -> EnterpriseWorkflowTemplate:
        """Return an exact or latest registered workflow template."""

        entry = self.get_entry(template_id, version)
        record = self._versioning.get(
            entry.template_id,
            entry.version,
        )
        return record.template

    def instantiate(
        self,
        template_id: str,
        *,
        version: str | None = None,
        context: dict[str, Any] | None = None,
        **template_arguments: Any,
    ) -> EnterpriseWorkflow:
        """Instantiate a registered workflow template."""

        entry = self.get_entry(template_id, version)
        template = self.get_template(
            entry.template_id,
            entry.version,
        )
        key = (entry.template_id, entry.version)
        safe_context = redact_mapping(context or {})

        with self._lock:
            factory = self._factories.get(key)

        if factory is not None:
            workflow = factory(template, safe_context)
            if not isinstance(workflow, EnterpriseWorkflow):
                raise TypeError(
                    "Workflow factory must return EnterpriseWorkflow."
                )
            return workflow

        merged_metadata = {
            **safe_context,
            **redact_mapping(
                template_arguments.pop("metadata", {}) or {}
            ),
        }

        return template.instantiate(
            metadata=merged_metadata,
            **template_arguments,
        )

    def list_entries(
        self,
        *,
        category: str | None = None,
        active_only: bool = False,
    ) -> tuple[EnterpriseWorkflowRegistryEntry, ...]:
        """Return registry entries with optional filtering."""

        cleaned_category = (
            str(category).strip()
            if category is not None
            else None
        )

        with self._lock:
            entries = list(self._entries.values())

        if cleaned_category is not None:
            entries = [
                entry
                for entry in entries
                if entry.category == cleaned_category
            ]

        if active_only:
            entries = [entry for entry in entries if entry.active]

        return tuple(
            sorted(
                entries,
                key=lambda item: (
                    item.category,
                    item.name,
                    item.template_id,
                    item.version,
                ),
            )
        )

    def has(
        self,
        template_id: str,
        version: str | None = None,
    ) -> bool:
        """Return whether a registry entry exists."""

        try:
            self.get_entry(template_id, version)
            return True
        except KeyError:
            return False

    def load_templates(
        self,
        templates: Iterable[EnterpriseWorkflowTemplate],
        *,
        created_by: str,
    ) -> None:
        """Register multiple templates."""

        for template in templates:
            self.register(
                template,
                created_by=created_by,
            )

    def clear(self) -> None:
        """Clear runtime registry entries and factories."""

        with self._lock:
            self._entries.clear()
            self._factories.clear()


_enterprise_workflow_registry: EnterpriseWorkflowRegistry | None = None
_enterprise_workflow_registry_lock = RLock()


def get_enterprise_workflow_registry() -> EnterpriseWorkflowRegistry:
    """Return the process-wide workflow registry."""

    global _enterprise_workflow_registry

    with _enterprise_workflow_registry_lock:
        if _enterprise_workflow_registry is None:
            _enterprise_workflow_registry = EnterpriseWorkflowRegistry()

        return _enterprise_workflow_registry