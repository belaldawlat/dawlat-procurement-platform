"""Thread-safe persistence for approval requests and policies."""

from __future__ import annotations

import threading

from app.orchestration.approval_models import (
    ApprovalRequest,
    ApprovalStatus,
)
from app.orchestration.approval_policy import (
    ApprovalPolicy,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


class InMemoryApprovalStore:
    """Thread-safe in-memory approval persistence."""

    def __init__(self) -> None:
        self._policies: dict[str, ApprovalPolicy] = {}
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    def register_policy(
        self,
        policy: ApprovalPolicy,
        *,
        replace_existing: bool = False,
    ) -> ApprovalPolicy:
        """Register an approval policy."""

        if not isinstance(policy, ApprovalPolicy):
            raise TypeError(
                "Approval store requires an ApprovalPolicy."
            )

        with self._lock:
            if (
                policy.policy_id in self._policies
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Approval policy "
                        f"{policy.policy_id!r} "
                        "already exists."
                    ),
                    metadata={
                        "policy_id": policy.policy_id,
                    },
                )

            self._policies[policy.policy_id] = policy

        return policy

    def get_policy(
        self,
        policy_id: str,
    ) -> ApprovalPolicy:
        """Return an exact approval policy."""

        cleaned_id = self._clean_identifier(
            policy_id,
            "Approval policy ID",
        )

        with self._lock:
            policy = self._policies.get(cleaned_id)

        if policy is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Approval policy {cleaned_id!r} "
                    "was not found."
                ),
                metadata={
                    "policy_id": cleaned_id,
                },
            )

        return policy

    def create_request(
        self,
        request: ApprovalRequest,
    ) -> ApprovalRequest:
        """Persist a new approval request."""

        if not isinstance(request, ApprovalRequest):
            raise TypeError(
                "Approval store requires an ApprovalRequest."
            )

        with self._lock:
            if request.request_id in self._requests:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Approval request "
                        f"{request.request_id!r} "
                        "already exists."
                    ),
                    metadata={
                        "request_id": request.request_id,
                    },
                )

            self._requests[request.request_id] = request

        return request

    def get_request(
        self,
        request_id: str,
    ) -> ApprovalRequest:
        """Return an exact approval request."""

        cleaned_id = self._clean_identifier(
            request_id,
            "Approval request ID",
        )

        with self._lock:
            request = self._requests.get(cleaned_id)

        if request is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Approval request {cleaned_id!r} "
                    "was not found."
                ),
                metadata={
                    "request_id": cleaned_id,
                },
            )

        return request

    def save_request(
        self,
        request: ApprovalRequest,
    ) -> ApprovalRequest:
        """Persist an updated approval request."""

        if not isinstance(request, ApprovalRequest):
            raise TypeError(
                "Approval store requires an ApprovalRequest."
            )

        with self._lock:
            if request.request_id not in self._requests:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Approval request "
                        f"{request.request_id!r} "
                        "was not found."
                    )
                )

            self._requests[request.request_id] = request

        return request

    def list_requests(
        self,
        *,
        status: ApprovalStatus | None = None,
        policy_id: str = "",
    ) -> tuple[ApprovalRequest, ...]:
        """Return requests in deterministic order."""

        cleaned_policy_id = str(policy_id or "").strip()

        with self._lock:
            requests = tuple(self._requests.values())

        filtered = [
            request
            for request in requests
            if (
                status is None
                or request.status is status
            )
            and (
                not cleaned_policy_id
                or request.policy_id
                == cleaned_policy_id
            )
        ]

        return tuple(
            sorted(
                filtered,
                key=lambda request: (
                    request.created_at,
                    request.request_id,
                ),
            )
        )

    def list_policies(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[ApprovalPolicy, ...]:
        """Return policies in deterministic order."""

        with self._lock:
            policies = tuple(self._policies.values())

        filtered = (
            tuple(
                policy
                for policy in policies
                if policy.enabled
            )
            if enabled_only
            else policies
        )

        return tuple(
            sorted(
                filtered,
                key=lambda policy: policy.policy_id,
            )
        )

    def clear(self) -> None:
        """Remove all policies and approval requests."""

        with self._lock:
            self._policies.clear()
            self._requests.clear()

    @staticmethod
    def _clean_identifier(
        value: str,
        label: str,
    ) -> str:
        cleaned = str(value or "").strip()

        if not cleaned:
            raise ValueError(f"{label} is required.")

        return cleaned


_default_approval_store = InMemoryApprovalStore()


def get_approval_store() -> InMemoryApprovalStore:
    """Return the shared approval store."""

    return _default_approval_store