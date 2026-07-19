"""Enterprise procurement orchestration coordinator."""

from __future__ import annotations

from app.orchestration.autonomous_procurement_models import (
    AutonomousAction,
)
from app.orchestration.enterprise_models import (
    EnterpriseCommand,
    EnterpriseOrchestrationSnapshot,
    EnterpriseStage,
)
from app.orchestration.enterprise_policy import (
    EnterpriseOrchestrationPolicy,
)
from app.orchestration.enterprise_result import (
    EnterpriseOrchestrationResult,
)
from app.orchestration.procurement_decision_models import (
    ProcurementDecision,
)


class EnterpriseOrchestrator:
    """Coordinate decision, intelligence and autonomous planning."""

    def __init__(
        self,
        policy: EnterpriseOrchestrationPolicy | None = None,
    ) -> None:
        self._policy = policy or EnterpriseOrchestrationPolicy(
            policy_id="default-enterprise-orchestration",
            name="Default Enterprise Orchestration Policy",
        )

    @property
    def policy(self) -> EnterpriseOrchestrationPolicy:
        return self._policy

    def coordinate(
        self,
        snapshot: EnterpriseOrchestrationSnapshot,
    ) -> EnterpriseOrchestrationResult:
        """Coordinate the procurement engines into one outcome."""

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise orchestration policy is disabled."
            )

        decision = snapshot.decision_result.decision
        base_command = self._policy.command_for_decision(decision)

        if decision is ProcurementDecision.REJECT:
            compensation_required = (
                self._policy.allow_compensation
                and snapshot.context.compensation_available
                and any(
                    action.action
                    is AutonomousAction.START_COMPENSATION
                    for action in snapshot.autonomous_result.actions
                )
            )

            return EnterpriseOrchestrationResult(
                case_id=snapshot.case_id,
                stage=(
                    EnterpriseStage.COMPENSATION_REQUIRED
                    if compensation_required
                    else EnterpriseStage.EXECUTION_BLOCKED
                ),
                command=(
                    EnterpriseCommand.START_COMPENSATION
                    if compensation_required
                    else EnterpriseCommand.REJECT
                ),
                successful=False,
                message=(
                    "Procurement rejected and compensation is required."
                    if compensation_required
                    else "Procurement rejected by enterprise controls."
                ),
                execution_allowed=False,
                compensation_required=compensation_required,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata=self._metadata(snapshot),
            )

        if (
            decision is ProcurementDecision.HOLD
            and self._policy.fail_closed_on_hold
        ):
            return EnterpriseOrchestrationResult(
                case_id=snapshot.case_id,
                stage=EnterpriseStage.EXECUTION_BLOCKED,
                command=EnterpriseCommand.HOLD,
                successful=False,
                message=(
                    "Procurement is on hold until blockers are resolved."
                ),
                execution_allowed=False,
                compensation_required=False,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata=self._metadata(snapshot),
            )

        if (
            decision is ProcurementDecision.MANUAL_REVIEW
            and self._policy.fail_closed_on_manual_review
        ):
            return EnterpriseOrchestrationResult(
                case_id=snapshot.case_id,
                stage=EnterpriseStage.APPROVAL_REQUIRED,
                command=EnterpriseCommand.MANUAL_REVIEW,
                successful=False,
                message=(
                    "Manual review is required before execution."
                ),
                execution_allowed=False,
                compensation_required=False,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata=self._metadata(snapshot),
            )

        if (
            self._policy.require_approval_before_execution
            and not snapshot.context.approval_satisfied
        ):
            return EnterpriseOrchestrationResult(
                case_id=snapshot.case_id,
                stage=EnterpriseStage.APPROVAL_REQUIRED,
                command=EnterpriseCommand.REQUEST_APPROVAL,
                successful=False,
                message=(
                    "Commercial approval is required before execution."
                ),
                execution_allowed=False,
                compensation_required=False,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata=self._metadata(snapshot),
            )

        if (
            snapshot.context.dry_run
            and not self._policy.allow_execution_in_dry_run
        ):
            return EnterpriseOrchestrationResult(
                case_id=snapshot.case_id,
                stage=EnterpriseStage.READY_FOR_EXECUTION,
                command=base_command,
                successful=True,
                message=(
                    "Procurement is ready, but dry-run mode prevents execution."
                ),
                execution_allowed=False,
                compensation_required=False,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata=self._metadata(snapshot),
            )

        if (
            snapshot.autonomous_result.confidence_score
            < self._policy.minimum_autonomous_confidence
        ):
            return EnterpriseOrchestrationResult(
                case_id=snapshot.case_id,
                stage=EnterpriseStage.APPROVAL_REQUIRED,
                command=EnterpriseCommand.MANUAL_REVIEW,
                successful=False,
                message=(
                    "Autonomous confidence is below the execution threshold."
                ),
                execution_allowed=False,
                compensation_required=False,
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata=self._metadata(snapshot),
            )

        execution_allowed = (
            snapshot.context.execution_requested
            and snapshot.autonomous_result.safe_to_execute
        )

        return EnterpriseOrchestrationResult(
            case_id=snapshot.case_id,
            stage=(
                EnterpriseStage.READY_FOR_EXECUTION
                if execution_allowed
                else EnterpriseStage.AUTONOMOUS_PLAN_CREATED
            ),
            command=(
                EnterpriseCommand.EXECUTE
                if execution_allowed
                else EnterpriseCommand.PROCEED
            ),
            successful=True,
            message=(
                "Enterprise procurement execution is authorised."
                if execution_allowed
                else "Enterprise procurement plan is ready."
            ),
            execution_allowed=execution_allowed,
            compensation_required=False,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata=self._metadata(snapshot),
        )

    @staticmethod
    def _metadata(
        snapshot: EnterpriseOrchestrationSnapshot,
    ) -> dict[str, object]:
        return {
            "decision": snapshot.decision_result.decision.value,
            "decision_score": snapshot.decision_result.score,
            "autonomous_confidence": (
                snapshot.autonomous_result.confidence_score
            ),
            "recommendation_count": len(
                snapshot.intelligence_result.recommendations
            ),
            "action_count": len(
                snapshot.autonomous_result.actions
            ),
            "actor_id": snapshot.context.actor_id,
            "correlation_id": snapshot.context.correlation_id,
        }


_default_enterprise_orchestrator = EnterpriseOrchestrator()


def get_enterprise_orchestrator() -> EnterpriseOrchestrator:
    return _default_enterprise_orchestrator