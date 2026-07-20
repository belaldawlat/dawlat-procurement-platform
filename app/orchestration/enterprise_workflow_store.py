"""Thread-safe persistence store for enterprise workflow instances.

Package V - Enterprise Workflow Intelligence.

The store deliberately provides an infrastructure-neutral, in-memory
implementation. It preserves immutable workflow domain objects, supports
optimistic concurrency, maintains append-only version history, and exposes
safe query and lifecycle operations. A durable repository can implement the
same public contract without changing orchestration callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable, Mapping

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowPriority,
    EnterpriseWorkflowStatus,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseWorkflowStoreRecord:
    """Immutable stored representation of one workflow revision."""

    workflow: EnterpriseWorkflow
    revision: int = 1
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    updated_at: str = dataclass_field(default_factory=utc_timestamp)
    created_by: str = "system"
    updated_by: str = "system"
    archived: bool = False
    archived_at: str = ""
    archived_by: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.workflow, EnterpriseWorkflow):
            raise TypeError(
                "Workflow store records require EnterpriseWorkflow."
            )
        if self.revision < 1:
            raise ValueError("Workflow store revision must be at least 1.")
        if not str(self.created_by or "").strip():
            raise ValueError("Workflow store creator is required.")
        if not str(self.updated_by or "").strip():
            raise ValueError("Workflow store updater is required.")
        if self.archived and not str(self.archived_at or "").strip():
            raise ValueError(
                "Archived workflow store records require archived_at."
            )
        if self.archived and not str(self.archived_by or "").strip():
            raise ValueError(
                "Archived workflow store records require archived_by."
            )

        object.__setattr__(
            self,
            "created_by",
            str(self.created_by).strip(),
        )
        object.__setattr__(
            self,
            "updated_by",
            str(self.updated_by).strip(),
        )
        object.__setattr__(
            self,
            "archived_at",
            str(self.archived_at or "").strip(),
        )
        object.__setattr__(
            self,
            "archived_by",
            str(self.archived_by or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def workflow_id(self) -> str:
        """Return the stored workflow identifier."""

        return self.workflow.workflow_id

    @property
    def case_id(self) -> str:
        """Return the stored case identifier."""

        return self.workflow.case_id

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "workflow": self.workflow.as_dict(),
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "archived": self.archived,
            "archived_at": self.archived_at,
            "archived_by": self.archived_by,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowStoreQuery:
    """Filtering and ordering criteria for workflow store searches."""

    case_id: str | None = None
    template_id: str | None = None
    statuses: tuple[EnterpriseWorkflowStatus, ...] = ()
    priorities: tuple[EnterpriseWorkflowPriority, ...] = ()
    include_archived: bool = False
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    limit: int | None = None
    offset: int = 0
    newest_first: bool = True

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValueError("Workflow store query limit must be positive.")
        if self.offset < 0:
            raise ValueError("Workflow store query offset cannot be negative.")

        object.__setattr__(
            self,
            "case_id",
            (
                str(self.case_id).strip()
                if self.case_id is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "template_id",
            (
                str(self.template_id).strip()
                if self.template_id is not None
                else None
            ),
        )
        object.__setattr__(self, "statuses", tuple(self.statuses))
        object.__setattr__(self, "priorities", tuple(self.priorities))
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )


class EnterpriseWorkflowStore:
    """Thread-safe workflow instance store with optimistic concurrency."""

    def __init__(self) -> None:
        self._records: dict[str, EnterpriseWorkflowStoreRecord] = {}
        self._history: dict[
            str,
            list[EnterpriseWorkflowStoreRecord],
        ] = {}
        self._lock = RLock()

    def create(
        self,
        workflow: EnterpriseWorkflow,
        *,
        actor_id: str = "system",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowStoreRecord:
        """Create a workflow record.

        Raises:
            ValueError: If the workflow already exists or inputs are invalid.
        """

        self._validate_workflow(workflow)
        actor = self._clean_actor(actor_id)
        timestamp = utc_timestamp()

        record = EnterpriseWorkflowStoreRecord(
            workflow=workflow,
            revision=1,
            created_at=timestamp,
            updated_at=timestamp,
            created_by=actor,
            updated_by=actor,
            metadata=redact_mapping(dict(metadata or {})),
        )

        with self._lock:
            if workflow.workflow_id in self._records:
                raise ValueError(
                    "Enterprise workflow already exists in the store."
                )

            self._records[workflow.workflow_id] = record
            self._history[workflow.workflow_id] = [record]

        return record

    def save(
        self,
        workflow: EnterpriseWorkflow,
        *,
        expected_revision: int | None = None,
        actor_id: str = "system",
        metadata: Mapping[str, Any] | None = None,
        create_if_missing: bool = False,
    ) -> EnterpriseWorkflowStoreRecord:
        """Create or update a workflow using optimistic concurrency.

        When ``expected_revision`` is supplied, the update fails unless it
        matches the current revision. Omitting it preserves compatibility
        with callers that previously performed unconditional saves.
        """

        self._validate_workflow(workflow)
        actor = self._clean_actor(actor_id)

        with self._lock:
            current = self._records.get(workflow.workflow_id)

            if current is None:
                if not create_if_missing:
                    raise KeyError(
                        "Enterprise workflow was not found in the store."
                    )
                return self.create(
                    workflow,
                    actor_id=actor,
                    metadata=metadata,
                )

            if current.archived:
                raise ValueError(
                    "Archived enterprise workflows cannot be updated."
                )

            if (
                expected_revision is not None
                and expected_revision != current.revision
            ):
                raise ValueError(
                    "Enterprise workflow revision conflict: "
                    f"expected {expected_revision}, "
                    f"found {current.revision}."
                )

            combined_metadata = {
                **redact_mapping(current.metadata),
                **redact_mapping(dict(metadata or {})),
            }

            updated = EnterpriseWorkflowStoreRecord(
                workflow=workflow,
                revision=current.revision + 1,
                created_at=current.created_at,
                updated_at=utc_timestamp(),
                created_by=current.created_by,
                updated_by=actor,
                metadata=combined_metadata,
            )

            self._records[workflow.workflow_id] = updated
            self._history.setdefault(workflow.workflow_id, []).append(
                updated
            )

            return updated

    def upsert(
        self,
        workflow: EnterpriseWorkflow,
        *,
        expected_revision: int | None = None,
        actor_id: str = "system",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowStoreRecord:
        """Create or update a workflow while preserving concurrency checks."""

        with self._lock:
            exists = workflow.workflow_id in self._records

        if not exists:
            if expected_revision not in {None, 0}:
                raise ValueError(
                    "A new enterprise workflow must use revision 0 or None."
                )
            return self.create(
                workflow,
                actor_id=actor_id,
                metadata=metadata,
            )

        return self.save(
            workflow,
            expected_revision=expected_revision,
            actor_id=actor_id,
            metadata=metadata,
        )

    def get_record(
        self,
        workflow_id: str,
        *,
        include_archived: bool = False,
    ) -> EnterpriseWorkflowStoreRecord:
        """Return the current record for a workflow."""

        cleaned_id = self._clean_workflow_id(workflow_id)

        with self._lock:
            record = self._records.get(cleaned_id)

        if record is None or (record.archived and not include_archived):
            raise KeyError(
                "Enterprise workflow was not found in the store."
            )

        return record

    def get(
        self,
        workflow_id: str,
        *,
        include_archived: bool = False,
    ) -> EnterpriseWorkflow:
        """Return the current workflow domain object."""

        return self.get_record(
            workflow_id,
            include_archived=include_archived,
        ).workflow

    def get_revision(
        self,
        workflow_id: str,
        revision: int,
    ) -> EnterpriseWorkflowStoreRecord:
        """Return an exact historical revision."""

        cleaned_id = self._clean_workflow_id(workflow_id)

        if revision < 1:
            raise ValueError("Workflow revision must be at least 1.")

        with self._lock:
            history = tuple(self._history.get(cleaned_id, ()))

        for record in history:
            if record.revision == revision:
                return record

        raise KeyError(
            "Enterprise workflow revision was not found in the store."
        )

    def history(
        self,
        workflow_id: str,
    ) -> tuple[EnterpriseWorkflowStoreRecord, ...]:
        """Return append-only revision history in ascending order."""

        cleaned_id = self._clean_workflow_id(workflow_id)

        with self._lock:
            records = tuple(self._history.get(cleaned_id, ()))

        if not records:
            raise KeyError(
                "Enterprise workflow was not found in the store."
            )

        return records

    def list_records(
        self,
        query: EnterpriseWorkflowStoreQuery | None = None,
        *,
        include_archived: bool | None = None,
    ) -> tuple[EnterpriseWorkflowStoreRecord, ...]:
        """Return records matching query criteria.

        ``include_archived`` is retained as a convenience/backward-compatible
        keyword and overrides the query setting when supplied.
        """

        criteria = query or EnterpriseWorkflowStoreQuery()

        if include_archived is not None:
            criteria = replace(
                criteria,
                include_archived=include_archived,
            )

        with self._lock:
            records = list(self._records.values())

        records = [
            record
            for record in records
            if self._matches(record, criteria)
        ]

        records.sort(
            key=lambda item: (
                item.updated_at,
                item.workflow_id,
            ),
            reverse=criteria.newest_first,
        )

        start = criteria.offset
        stop = (
            start + criteria.limit
            if criteria.limit is not None
            else None
        )

        return tuple(records[start:stop])

    def list_workflows(
        self,
        query: EnterpriseWorkflowStoreQuery | None = None,
        *,
        include_archived: bool | None = None,
    ) -> tuple[EnterpriseWorkflow, ...]:
        """Return workflow objects matching query criteria."""

        return tuple(
            record.workflow
            for record in self.list_records(
                query,
                include_archived=include_archived,
            )
        )

    def find_by_case(
        self,
        case_id: str,
        *,
        include_archived: bool = False,
    ) -> tuple[EnterpriseWorkflow, ...]:
        """Return all workflows for one business case."""

        cleaned_case_id = str(case_id or "").strip()

        if not cleaned_case_id:
            raise ValueError("Enterprise workflow case ID is required.")

        return self.list_workflows(
            EnterpriseWorkflowStoreQuery(
                case_id=cleaned_case_id,
                include_archived=include_archived,
            )
        )

    def archive(
        self,
        workflow_id: str,
        *,
        actor_id: str = "system",
        expected_revision: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowStoreRecord:
        """Archive a workflow without deleting its history."""

        cleaned_id = self._clean_workflow_id(workflow_id)
        actor = self._clean_actor(actor_id)

        with self._lock:
            current = self._records.get(cleaned_id)

            if current is None:
                raise KeyError(
                    "Enterprise workflow was not found in the store."
                )
            if current.archived:
                return current
            if (
                expected_revision is not None
                and expected_revision != current.revision
            ):
                raise ValueError(
                    "Enterprise workflow revision conflict: "
                    f"expected {expected_revision}, "
                    f"found {current.revision}."
                )

            timestamp = utc_timestamp()
            archived_workflow = replace(
                current.workflow,
                status=EnterpriseWorkflowStatus.ARCHIVED,
            )
            archived = EnterpriseWorkflowStoreRecord(
                workflow=archived_workflow,
                revision=current.revision + 1,
                created_at=current.created_at,
                updated_at=timestamp,
                created_by=current.created_by,
                updated_by=actor,
                archived=True,
                archived_at=timestamp,
                archived_by=actor,
                metadata={
                    **redact_mapping(current.metadata),
                    **redact_mapping(dict(metadata or {})),
                },
            )

            self._records[cleaned_id] = archived
            self._history.setdefault(cleaned_id, []).append(archived)

            return archived

    def restore(
        self,
        workflow_id: str,
        *,
        actor_id: str = "system",
        expected_revision: int | None = None,
        status: EnterpriseWorkflowStatus = (
            EnterpriseWorkflowStatus.PAUSED
        ),
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowStoreRecord:
        """Restore an archived workflow to a non-archived lifecycle state."""

        if status is EnterpriseWorkflowStatus.ARCHIVED:
            raise ValueError(
                "Restored workflow status cannot remain archived."
            )

        cleaned_id = self._clean_workflow_id(workflow_id)
        actor = self._clean_actor(actor_id)

        with self._lock:
            current = self._records.get(cleaned_id)

            if current is None:
                raise KeyError(
                    "Enterprise workflow was not found in the store."
                )
            if not current.archived:
                return current
            if (
                expected_revision is not None
                and expected_revision != current.revision
            ):
                raise ValueError(
                    "Enterprise workflow revision conflict: "
                    f"expected {expected_revision}, "
                    f"found {current.revision}."
                )

            restored = EnterpriseWorkflowStoreRecord(
                workflow=replace(current.workflow, status=status),
                revision=current.revision + 1,
                created_at=current.created_at,
                updated_at=utc_timestamp(),
                created_by=current.created_by,
                updated_by=actor,
                metadata={
                    **redact_mapping(current.metadata),
                    **redact_mapping(dict(metadata or {})),
                },
            )

            self._records[cleaned_id] = restored
            self._history.setdefault(cleaned_id, []).append(restored)

            return restored

    def delete(
        self,
        workflow_id: str,
        *,
        expected_revision: int | None = None,
    ) -> EnterpriseWorkflowStoreRecord:
        """Permanently remove a workflow and its history.

        Prefer :meth:`archive` for normal business lifecycle operations.
        This method exists for tests, ephemeral stores, and administrative
        data-retention enforcement.
        """

        cleaned_id = self._clean_workflow_id(workflow_id)

        with self._lock:
            current = self._records.get(cleaned_id)

            if current is None:
                raise KeyError(
                    "Enterprise workflow was not found in the store."
                )
            if (
                expected_revision is not None
                and expected_revision != current.revision
            ):
                raise ValueError(
                    "Enterprise workflow revision conflict: "
                    f"expected {expected_revision}, "
                    f"found {current.revision}."
                )

            removed = self._records.pop(cleaned_id)
            self._history.pop(cleaned_id, None)

        return removed

    def exists(
        self,
        workflow_id: str,
        *,
        include_archived: bool = False,
    ) -> bool:
        """Return whether a workflow currently exists."""

        try:
            self.get_record(
                workflow_id,
                include_archived=include_archived,
            )
            return True
        except (KeyError, ValueError):
            return False

    def count(
        self,
        query: EnterpriseWorkflowStoreQuery | None = None,
        *,
        include_archived: bool | None = None,
    ) -> int:
        """Return the number of matching current records."""

        return len(
            self.list_records(
                query,
                include_archived=include_archived,
            )
        )

    def load(
        self,
        workflows: Iterable[EnterpriseWorkflow],
        *,
        actor_id: str = "system",
        replace_existing: bool = False,
    ) -> tuple[EnterpriseWorkflowStoreRecord, ...]:
        """Bulk-load workflows using deterministic input order."""

        loaded: list[EnterpriseWorkflowStoreRecord] = []

        for workflow in workflows:
            if self.exists(workflow.workflow_id, include_archived=True):
                if not replace_existing:
                    raise ValueError(
                        "Enterprise workflow already exists in the store."
                    )
                current = self.get_record(
                    workflow.workflow_id,
                    include_archived=True,
                )
                if current.archived:
                    self.restore(
                        workflow.workflow_id,
                        actor_id=actor_id,
                        expected_revision=current.revision,
                    )
                    current = self.get_record(workflow.workflow_id)

                loaded.append(
                    self.save(
                        workflow,
                        expected_revision=current.revision,
                        actor_id=actor_id,
                    )
                )
            else:
                loaded.append(
                    self.create(
                        workflow,
                        actor_id=actor_id,
                    )
                )

        return tuple(loaded)

    def clear(self) -> None:
        """Clear all current records and history."""

        with self._lock:
            self._records.clear()
            self._history.clear()

    @staticmethod
    def _validate_workflow(workflow: EnterpriseWorkflow) -> None:
        if not isinstance(workflow, EnterpriseWorkflow):
            raise TypeError(
                "Enterprise workflow store requires EnterpriseWorkflow."
            )

    @staticmethod
    def _clean_workflow_id(workflow_id: str) -> str:
        cleaned_id = str(workflow_id or "").strip()

        if not cleaned_id:
            raise ValueError("Enterprise workflow ID is required.")

        return cleaned_id

    @staticmethod
    def _clean_actor(actor_id: str) -> str:
        actor = str(actor_id or "").strip()

        if not actor:
            raise ValueError("Enterprise workflow store actor is required.")

        return actor

    @staticmethod
    def _matches(
        record: EnterpriseWorkflowStoreRecord,
        query: EnterpriseWorkflowStoreQuery,
    ) -> bool:
        workflow = record.workflow

        if record.archived and not query.include_archived:
            return False
        if query.case_id is not None and workflow.case_id != query.case_id:
            return False
        if (
            query.template_id is not None
            and workflow.template_id != query.template_id
        ):
            return False
        if query.statuses and workflow.status not in query.statuses:
            return False
        if query.priorities and workflow.priority not in query.priorities:
            return False

        safe_metadata = redact_mapping(workflow.metadata)
        store_metadata = redact_mapping(record.metadata)

        for key, value in query.metadata.items():
            if (
                safe_metadata.get(key) != value
                and store_metadata.get(key) != value
            ):
                return False

        return True


_enterprise_workflow_store: EnterpriseWorkflowStore | None = None
_enterprise_workflow_store_lock = RLock()


def get_enterprise_workflow_store() -> EnterpriseWorkflowStore:
    """Return the process-wide enterprise workflow store."""

    global _enterprise_workflow_store

    with _enterprise_workflow_store_lock:
        if _enterprise_workflow_store is None:
            _enterprise_workflow_store = EnterpriseWorkflowStore()

        return _enterprise_workflow_store


# Backward-compatible aliases retained for earlier Package V callers.
WorkflowStore = EnterpriseWorkflowStore
WorkflowStoreRecord = EnterpriseWorkflowStoreRecord
WorkflowStoreQuery = EnterpriseWorkflowStoreQuery