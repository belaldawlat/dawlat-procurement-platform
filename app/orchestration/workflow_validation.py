"""Deterministic validation for workflow definitions."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.workflow_models import (
    FailureStrategy,
    WorkflowDefinition,
)


@dataclass(frozen=True)
class ValidationIssue:
    """A deterministic workflow validation issue."""

    code: str
    message: str
    field: str = ""
    step_id: str = ""


@dataclass(frozen=True)
class WorkflowValidationResult:
    """Complete validation outcome for a workflow definition."""

    valid: bool
    issues: tuple[ValidationIssue, ...]

    @property
    def error_count(self) -> int:
        """Return the number of validation issues."""

        return len(self.issues)


class WorkflowDefinitionValidator:
    """Validate structural integrity of workflow definitions."""

    def validate(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowValidationResult:
        """Return all deterministic validation issues."""

        issues: list[ValidationIssue] = []

        self._validate_identity(definition, issues)
        self._validate_steps(definition, issues)
        self._validate_dependencies(definition, issues)
        self._validate_entry_and_terminal_steps(
            definition,
            issues,
        )
        self._validate_compensation(definition, issues)
        self._validate_cycles(definition, issues)

        ordered_issues = tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.code,
                    issue.step_id,
                    issue.field,
                    issue.message,
                ),
            )
        )

        return WorkflowValidationResult(
            valid=not ordered_issues,
            issues=ordered_issues,
        )

    @staticmethod
    def _validate_identity(
        definition: WorkflowDefinition,
        issues: list[ValidationIssue],
    ) -> None:
        if not definition.workflow_id:
            issues.append(
                ValidationIssue(
                    code="WORKFLOW_ID_REQUIRED",
                    message="Workflow ID is required.",
                    field="workflow_id",
                )
            )

        if not definition.name:
            issues.append(
                ValidationIssue(
                    code="WORKFLOW_NAME_REQUIRED",
                    message="Workflow name is required.",
                    field="name",
                )
            )

        if not definition.version:
            issues.append(
                ValidationIssue(
                    code="WORKFLOW_VERSION_REQUIRED",
                    message="Workflow version is required.",
                    field="version",
                )
            )

    @staticmethod
    def _validate_steps(
        definition: WorkflowDefinition,
        issues: list[ValidationIssue],
    ) -> None:
        if not definition.steps:
            issues.append(
                ValidationIssue(
                    code="WORKFLOW_STEPS_REQUIRED",
                    message=(
                        "At least one workflow step is required."
                    ),
                    field="steps",
                )
            )
            return

        seen: set[str] = set()

        for step in definition.steps:
            if not step.step_id:
                issues.append(
                    ValidationIssue(
                        code="STEP_ID_REQUIRED",
                        message="Workflow step ID is required.",
                        field="step_id",
                    )
                )
                continue

            if step.step_id in seen:
                issues.append(
                    ValidationIssue(
                        code="DUPLICATE_STEP_ID",
                        message=(
                            f"Duplicate workflow step ID: "
                            f"{step.step_id}."
                        ),
                        step_id=step.step_id,
                    )
                )

            seen.add(step.step_id)

            if not step.name:
                issues.append(
                    ValidationIssue(
                        code="STEP_NAME_REQUIRED",
                        message="Workflow step name is required.",
                        field="name",
                        step_id=step.step_id,
                    )
                )

            if step.maximum_attempts < 1:
                issues.append(
                    ValidationIssue(
                        code="INVALID_MAXIMUM_ATTEMPTS",
                        message=(
                            "Maximum attempts must be at least 1."
                        ),
                        field="maximum_attempts",
                        step_id=step.step_id,
                    )
                )

            if (
                step.timeout_seconds is not None
                and step.timeout_seconds <= 0
            ):
                issues.append(
                    ValidationIssue(
                        code="INVALID_STEP_TIMEOUT",
                        message=(
                            "Step timeout must be greater than 0."
                        ),
                        field="timeout_seconds",
                        step_id=step.step_id,
                    )
                )

    @staticmethod
    def _validate_dependencies(
        definition: WorkflowDefinition,
        issues: list[ValidationIssue],
    ) -> None:
        step_ids = set(definition.step_ids)

        for step in definition.steps:
            if len(step.dependencies) != len(
                set(step.dependencies)
            ):
                issues.append(
                    ValidationIssue(
                        code="DUPLICATE_STEP_DEPENDENCY",
                        message=(
                            "A workflow step contains duplicate "
                            "dependencies."
                        ),
                        field="dependencies",
                        step_id=step.step_id,
                    )
                )

            for dependency in step.dependencies:
                if dependency == step.step_id:
                    issues.append(
                        ValidationIssue(
                            code="SELF_DEPENDENCY",
                            message=(
                                "A workflow step cannot depend "
                                "on itself."
                            ),
                            field="dependencies",
                            step_id=step.step_id,
                        )
                    )
                elif dependency not in step_ids:
                    issues.append(
                        ValidationIssue(
                            code="UNKNOWN_STEP_DEPENDENCY",
                            message=(
                                f"Unknown dependency: {dependency}."
                            ),
                            field="dependencies",
                            step_id=step.step_id,
                        )
                    )

    @staticmethod
    def _validate_entry_and_terminal_steps(
        definition: WorkflowDefinition,
        issues: list[ValidationIssue],
    ) -> None:
        step_ids = set(definition.step_ids)

        if (
            definition.initial_step_id
            and definition.initial_step_id not in step_ids
        ):
            issues.append(
                ValidationIssue(
                    code="UNKNOWN_INITIAL_STEP",
                    message=(
                        "Initial step does not exist in the "
                        "workflow definition."
                    ),
                    field="initial_step_id",
                )
            )

        if definition.steps and not definition.initial_step_id:
            root_steps = [
                step.step_id
                for step in definition.steps
                if not step.dependencies
            ]

            if len(root_steps) != 1:
                issues.append(
                    ValidationIssue(
                        code="AMBIGUOUS_INITIAL_STEP",
                        message=(
                            "Workflow must define an initial step "
                            "when there is not exactly one root step."
                        ),
                        field="initial_step_id",
                    )
                )

        for terminal_step_id in definition.terminal_step_ids:
            if terminal_step_id not in step_ids:
                issues.append(
                    ValidationIssue(
                        code="UNKNOWN_TERMINAL_STEP",
                        message=(
                            f"Unknown terminal step: "
                            f"{terminal_step_id}."
                        ),
                        field="terminal_step_ids",
                    )
                )

    @staticmethod
    def _validate_compensation(
        definition: WorkflowDefinition,
        issues: list[ValidationIssue],
    ) -> None:
        step_ids = set(definition.step_ids)

        for step in definition.steps:
            if (
                step.failure_strategy
                is FailureStrategy.COMPENSATE
                and not step.compensation_step_id
            ):
                issues.append(
                    ValidationIssue(
                        code="COMPENSATION_STEP_REQUIRED",
                        message=(
                            "Compensation strategy requires a "
                            "compensation step."
                        ),
                        field="compensation_step_id",
                        step_id=step.step_id,
                    )
                )

            if (
                step.compensation_step_id
                and step.compensation_step_id not in step_ids
            ):
                issues.append(
                    ValidationIssue(
                        code="UNKNOWN_COMPENSATION_STEP",
                        message=(
                            f"Unknown compensation step: "
                            f"{step.compensation_step_id}."
                        ),
                        field="compensation_step_id",
                        step_id=step.step_id,
                    )
                )

            if step.compensation_step_id == step.step_id:
                issues.append(
                    ValidationIssue(
                        code="SELF_COMPENSATION",
                        message=(
                            "A workflow step cannot compensate itself."
                        ),
                        field="compensation_step_id",
                        step_id=step.step_id,
                    )
                )

    @staticmethod
    def _validate_cycles(
        definition: WorkflowDefinition,
        issues: list[ValidationIssue],
    ) -> None:
        graph = {
            step.step_id: tuple(step.dependencies)
            for step in definition.steps
            if step.step_id
        }

        visiting: set[str] = set()
        visited: set[str] = set()
        cycle_nodes: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visited:
                return

            if step_id in visiting:
                cycle_nodes.add(step_id)
                return

            visiting.add(step_id)

            for dependency in graph.get(step_id, ()):
                if dependency in graph:
                    visit(dependency)

            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in sorted(graph):
            visit(step_id)

        if cycle_nodes:
            issues.append(
                ValidationIssue(
                    code="CYCLIC_DEPENDENCY",
                    message=(
                        "Workflow dependency graph contains a cycle."
                    ),
                    field="steps",
                )
            )


_default_validator = WorkflowDefinitionValidator()


def validate_workflow_definition(
    definition: WorkflowDefinition,
) -> WorkflowValidationResult:
    """Validate a workflow using the shared validator."""

    return _default_validator.validate(definition)