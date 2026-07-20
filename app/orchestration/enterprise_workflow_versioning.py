"""Version management for enterprise workflow templates."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_template import (
    EnterpriseWorkflowTemplate,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, order=True)
class EnterpriseWorkflowSemanticVersion:
    """Validated semantic version value."""

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Semantic version values cannot be negative.")

    @classmethod
    def parse(cls, value: str) -> "EnterpriseWorkflowSemanticVersion":
        """Parse a strict ``major.minor.patch`` version string."""

        cleaned = str(value or "").strip()
        parts = cleaned.split(".")

        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise ValueError(
                "Workflow template version must use major.minor.patch."
            )

        return cls(*(int(part) for part in parts))

    def bump_major(self) -> "EnterpriseWorkflowSemanticVersion":
        """Return the next major version."""

        return type(self)(self.major + 1, 0, 0)

    def bump_minor(self) -> "EnterpriseWorkflowSemanticVersion":
        """Return the next minor version."""

        return type(self)(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "EnterpriseWorkflowSemanticVersion":
        """Return the next patch version."""

        return type(self)(self.major, self.minor, self.patch + 1)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class EnterpriseWorkflowTemplateVersion:
    """One immutable versioned workflow template record."""

    template: EnterpriseWorkflowTemplate
    version: EnterpriseWorkflowSemanticVersion
    change_summary: str
    created_by: str
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    supersedes_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.template.version != str(self.version):
            raise ValueError(
                "Template version must match the version record."
            )
        if not str(self.change_summary or "").strip():
            raise ValueError("Workflow version change summary is required.")
        if not str(self.created_by or "").strip():
            raise ValueError("Workflow version creator is required.")

        object.__setattr__(
            self,
            "change_summary",
            str(self.change_summary).strip(),
        )
        object.__setattr__(
            self,
            "created_by",
            str(self.created_by).strip(),
        )
        object.__setattr__(
            self,
            "supersedes_version",
            str(self.supersedes_version or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "template": self.template.as_dict(),
            "version": str(self.version),
            "change_summary": self.change_summary,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "supersedes_version": self.supersedes_version,
            "metadata": redact_mapping(self.metadata),
        }


class EnterpriseWorkflowVersioning:
    """Thread-safe workflow template version manager."""

    def __init__(self) -> None:
        self._versions: dict[
            str,
            dict[str, EnterpriseWorkflowTemplateVersion],
        ] = {}
        self._lock = RLock()

    def register_initial(
        self,
        template: EnterpriseWorkflowTemplate,
        *,
        created_by: str,
        change_summary: str = "Initial workflow template version.",
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseWorkflowTemplateVersion:
        """Register the first version of a workflow template."""

        semantic_version = EnterpriseWorkflowSemanticVersion.parse(
            template.version
        )

        with self._lock:
            existing = self._versions.get(template.template_id, {})
            if existing:
                raise ValueError(
                    "Workflow template already has registered versions."
                )

            record = EnterpriseWorkflowTemplateVersion(
                template=template,
                version=semantic_version,
                change_summary=change_summary,
                created_by=created_by,
                metadata=metadata or {},
            )
            self._versions[template.template_id] = {
                str(semantic_version): record
            }
            return record

    def create_version(
        self,
        template: EnterpriseWorkflowTemplate,
        *,
        bump: str,
        created_by: str,
        change_summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseWorkflowTemplateVersion:
        """Create a new immutable version from the latest registered version."""

        bump_name = str(bump or "").strip().lower()
        if bump_name not in {"major", "minor", "patch"}:
            raise ValueError("Version bump must be major, minor or patch.")

        with self._lock:
            latest = self.get_latest(template.template_id)
            current = latest.version

            next_version = {
                "major": current.bump_major,
                "minor": current.bump_minor,
                "patch": current.bump_patch,
            }[bump_name]()

            if template.template_id != latest.template.template_id:
                raise ValueError(
                    "Versioned template ID cannot change."
                )

            versioned_template = replace(
                template,
                version=str(next_version),
                created_at=utc_timestamp(),
            )
            record = EnterpriseWorkflowTemplateVersion(
                template=versioned_template,
                version=next_version,
                change_summary=change_summary,
                created_by=created_by,
                supersedes_version=str(current),
                metadata=metadata or {},
            )
            self._versions[template.template_id][str(next_version)] = record
            return record

    def register_explicit(
        self,
        record: EnterpriseWorkflowTemplateVersion,
    ) -> EnterpriseWorkflowTemplateVersion:
        """Register a pre-built version record after validating continuity."""

        with self._lock:
            bucket = self._versions.setdefault(
                record.template.template_id,
                {},
            )
            key = str(record.version)

            if key in bucket:
                raise ValueError(
                    "Workflow template version is already registered."
                )

            if bucket and record.supersedes_version:
                if record.supersedes_version not in bucket:
                    raise ValueError(
                        "Superseded workflow version does not exist."
                    )

            bucket[key] = record
            return record

    def get(
        self,
        template_id: str,
        version: str,
    ) -> EnterpriseWorkflowTemplateVersion:
        """Return one exact workflow template version."""

        cleaned_id = str(template_id or "").strip()
        cleaned_version = str(
            EnterpriseWorkflowSemanticVersion.parse(version)
        )

        with self._lock:
            try:
                return self._versions[cleaned_id][cleaned_version]
            except KeyError as exc:
                raise KeyError(
                    "Workflow template version was not found."
                ) from exc

    def get_latest(
        self,
        template_id: str,
    ) -> EnterpriseWorkflowTemplateVersion:
        """Return the highest semantic version for a template."""

        cleaned_id = str(template_id or "").strip()

        with self._lock:
            bucket = self._versions.get(cleaned_id)
            if not bucket:
                raise KeyError(
                    "Workflow template has no registered versions."
                )

            return max(
                bucket.values(),
                key=lambda record: record.version,
            )

    def list_versions(
        self,
        template_id: str,
    ) -> tuple[EnterpriseWorkflowTemplateVersion, ...]:
        """Return all versions in ascending semantic-version order."""

        cleaned_id = str(template_id or "").strip()

        with self._lock:
            bucket = self._versions.get(cleaned_id, {})
            return tuple(
                sorted(
                    bucket.values(),
                    key=lambda record: record.version,
                )
            )

    def list_template_ids(self) -> tuple[str, ...]:
        """Return all template IDs with version history."""

        with self._lock:
            return tuple(sorted(self._versions))

    def has_version(self, template_id: str, version: str) -> bool:
        """Return whether an exact template version exists."""

        try:
            self.get(template_id, version)
            return True
        except (KeyError, ValueError):
            return False

    def load_records(
        self,
        records: Iterable[EnterpriseWorkflowTemplateVersion],
    ) -> None:
        """Load multiple records using explicit registration rules."""

        for record in records:
            self.register_explicit(record)

    def clear(self) -> None:
        """Remove all in-memory version records."""

        with self._lock:
            self._versions.clear()


_enterprise_workflow_versioning: EnterpriseWorkflowVersioning | None = None
_enterprise_workflow_versioning_lock = RLock()


def get_enterprise_workflow_versioning() -> EnterpriseWorkflowVersioning:
    """Return the process-wide workflow version manager."""

    global _enterprise_workflow_versioning

    with _enterprise_workflow_versioning_lock:
        if _enterprise_workflow_versioning is None:
            _enterprise_workflow_versioning = EnterpriseWorkflowVersioning()

        return _enterprise_workflow_versioning