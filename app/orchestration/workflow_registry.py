"""Thread-safe registry for versioned workflow definitions."""

from __future__ import annotations

import threading

from app.observability.logging_config import get_logger
from app.orchestration.exceptions import (
    DuplicateWorkflowError,
    WorkflowNotFoundError,
    WorkflowRegistrationError,
    WorkflowValidationError,
)
from app.orchestration.workflow_models import (
    WorkflowDefinition,
)
from app.orchestration.workflow_validation import (
    WorkflowDefinitionValidator,
)


class WorkflowRegistry:
    """Store immutable versioned workflow definitions."""

    def __init__(
        self,
        validator: WorkflowDefinitionValidator | None = None,
    ) -> None:
        self._validator = (
            validator or WorkflowDefinitionValidator()
        )
        self._definitions: dict[
            str,
            WorkflowDefinition,
        ] = {}
        self._lock = threading.RLock()
        self._logger = get_logger(
            "orchestration.workflow_registry"
        )

    def register(
        self,
        definition: WorkflowDefinition,
        *,
        replace_existing: bool = False,
    ) -> WorkflowDefinition:
        """Validate and register a workflow definition."""

        if not isinstance(definition, WorkflowDefinition):
            raise WorkflowRegistrationError(
                technical_message=(
                    "Registry accepts WorkflowDefinition objects only."
                )
            )

        validation = self._validator.validate(definition)

        if not validation.valid:
            raise WorkflowValidationError(
                technical_message=(
                    "Workflow definition validation failed."
                ),
                metadata={
                    "workflow_id": definition.workflow_id,
                    "workflow_version": definition.version,
                    "issues": [
                        {
                            "code": issue.code,
                            "field": issue.field,
                            "step_id": issue.step_id,
                            "message": issue.message,
                        }
                        for issue in validation.issues
                    ],
                },
            )

        key = definition.registry_key

        with self._lock:
            if (
                key in self._definitions
                and not replace_existing
            ):
                raise DuplicateWorkflowError(
                    technical_message=(
                        f"Workflow {key!r} is already registered."
                    ),
                    metadata={
                        "registry_key": key,
                    },
                )

            self._definitions[key] = definition

        self._logger.info(
            "Workflow definition registered.",
            extra={
                "workflow_id": definition.workflow_id,
                "workflow_version": definition.version,
                "step_count": len(definition.steps),
                "replace_existing": replace_existing,
            },
        )

        return definition

    def get(
        self,
        workflow_id: str,
        version: str,
    ) -> WorkflowDefinition:
        """Return an exact workflow definition."""

        key = self._build_key(workflow_id, version)

        with self._lock:
            definition = self._definitions.get(key)

        if definition is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Workflow {key!r} was not found."
                ),
                metadata={
                    "registry_key": key,
                },
            )

        return definition

    def get_latest(
        self,
        workflow_id: str,
    ) -> WorkflowDefinition:
        """Return the latest registered version deterministically."""

        cleaned_id = str(workflow_id or "").strip()

        if not cleaned_id:
            raise ValueError("Workflow ID is required.")

        with self._lock:
            matches = [
                definition
                for definition in self._definitions.values()
                if definition.workflow_id == cleaned_id
            ]

        if not matches:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"No workflow versions found for "
                    f"{cleaned_id!r}."
                ),
                metadata={
                    "workflow_id": cleaned_id,
                },
            )

        return sorted(
            matches,
            key=lambda definition: definition.version,
        )[-1]

    def list_definitions(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[WorkflowDefinition, ...]:
        """Return definitions in deterministic order."""

        with self._lock:
            definitions = tuple(
                self._definitions.values()
            )

        filtered = (
            tuple(
                definition
                for definition in definitions
                if definition.enabled
            )
            if enabled_only
            else definitions
        )

        return tuple(
            sorted(
                filtered,
                key=lambda definition: (
                    definition.workflow_id,
                    definition.version,
                ),
            )
        )

    def unregister(
        self,
        workflow_id: str,
        version: str,
    ) -> WorkflowDefinition:
        """Remove and return a workflow definition."""

        key = self._build_key(workflow_id, version)

        with self._lock:
            definition = self._definitions.pop(key, None)

        if definition is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Workflow {key!r} was not found."
                ),
                metadata={
                    "registry_key": key,
                },
            )

        self._logger.warning(
            "Workflow definition unregistered.",
            extra={
                "workflow_id": definition.workflow_id,
                "workflow_version": definition.version,
            },
        )

        return definition

    def contains(
        self,
        workflow_id: str,
        version: str,
    ) -> bool:
        """Return whether an exact workflow is registered."""

        key = self._build_key(workflow_id, version)

        with self._lock:
            return key in self._definitions

    def clear(self) -> None:
        """Remove all workflow definitions."""

        with self._lock:
            self._definitions.clear()

    @staticmethod
    def _build_key(
        workflow_id: str,
        version: str,
    ) -> str:
        cleaned_id = str(workflow_id or "").strip()
        cleaned_version = str(version or "").strip()

        if not cleaned_id:
            raise ValueError("Workflow ID is required.")

        if not cleaned_version:
            raise ValueError("Workflow version is required.")

        return f"{cleaned_id}:{cleaned_version}"


_default_registry = WorkflowRegistry()


def get_workflow_registry() -> WorkflowRegistry:
    """Return the shared workflow registry."""

    return _default_registry