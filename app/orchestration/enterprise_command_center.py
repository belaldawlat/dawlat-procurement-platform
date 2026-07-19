"""Executive command center for enterprise procurement operations."""

from __future__ import annotations

from app.orchestration.enterprise_command_models import (
    CommandCenterDomain,
    CommandCenterHealth,
    CommandCenterPriority,
    EnterpriseCommandSnapshot,
    ExecutiveAction,
    ExecutiveDirective,
    ExecutiveKPI,
)
from app.orchestration.enterprise_command_policy import (
    EnterpriseCommandPolicy,
)
from app.orchestration.enterprise_command_result import (
    EnterpriseCommandResult,
)


class EnterpriseCommandCenter:
    """Evaluate portfolio health and generate executive directives."""

    def __init__(
        self,
        policy: EnterpriseCommandPolicy | None = None,
    ) -> None:
        self._policy = policy or EnterpriseCommandPolicy(
            policy_id="default-enterprise-command",
            name="Default Enterprise Command Policy",
        )

    @property
    def policy(self) -> EnterpriseCommandPolicy:
        return self._policy

    def evaluate(
        self,
        snapshot: EnterpriseCommandSnapshot,
    ) -> EnterpriseCommandResult:
        if not isinstance(snapshot, EnterpriseCommandSnapshot):
            raise TypeError(
                "Command center requires an EnterpriseCommandSnapshot."
            )

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise command policy is disabled."
            )

        kpis = self._build_kpis(snapshot)
        directives = self._build_directives(snapshot)
        health_score = self._calculate_health_score(snapshot, directives)
        health = self._resolve_health(health_score, directives)
        execution_paused = any(
            directive.blocking
            for directive in directives
        )

        return EnterpriseCommandResult(
            portfolio_id=snapshot.portfolio_id,
            health=health,
            health_score=health_score,
            kpis=kpis,
            directives=directives,
            execution_paused=execution_paused,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "active_procurements": snapshot.active_procurements,
                "directive_count": len(directives),
                "kpi_count": len(kpis),
            },
        )

    def _build_kpis(
        self,
        snapshot: EnterpriseCommandSnapshot,
    ) -> tuple[ExecutiveKPI, ...]:
        exposure_ratio = (
            snapshot.financial_exposure / snapshot.procurement_value
            if snapshot.procurement_value > 0
            else 0.0
        )

        return (
            ExecutiveKPI(
                kpi_id="active-procurements",
                name="Active Procurements",
                domain=CommandCenterDomain.PROCUREMENT,
                value=float(snapshot.active_procurements),
                unit="count",
            ),
            ExecutiveKPI(
                kpi_id="blocked-procurements",
                name="Blocked Procurements",
                domain=CommandCenterDomain.EXECUTION,
                value=float(snapshot.blocked_procurements),
                unit="count",
                target=0,
            ),
            ExecutiveKPI(
                kpi_id="decision-score",
                name="Average Decision Score",
                domain=CommandCenterDomain.PROCUREMENT,
                value=snapshot.average_decision_score,
                unit="score",
                target=self._policy.minimum_decision_score,
            ),
            ExecutiveKPI(
                kpi_id="autonomous-confidence",
                name="Average Autonomous Confidence",
                domain=CommandCenterDomain.AUTONOMY,
                value=snapshot.average_autonomous_confidence,
                unit="score",
                target=self._policy.minimum_autonomous_confidence,
            ),
            ExecutiveKPI(
                kpi_id="payment-clearance-rate",
                name="Payment Clearance Rate",
                domain=CommandCenterDomain.FINANCIAL,
                value=snapshot.payment_clearance_rate,
                unit="percent",
                target=self._policy.minimum_payment_clearance_rate,
            ),
            ExecutiveKPI(
                kpi_id="document-completeness-rate",
                name="Document Completeness Rate",
                domain=CommandCenterDomain.COMPLIANCE,
                value=snapshot.document_completeness_rate,
                unit="percent",
                target=(
                    self._policy.minimum_document_completeness_rate
                ),
            ),
            ExecutiveKPI(
                kpi_id="on-time-shipment-rate",
                name="On-Time Shipment Rate",
                domain=CommandCenterDomain.SHIPMENT,
                value=snapshot.on_time_shipment_rate,
                unit="percent",
                target=self._policy.minimum_on_time_shipment_rate,
            ),
            ExecutiveKPI(
                kpi_id="financial-exposure-ratio",
                name="Financial Exposure Ratio",
                domain=CommandCenterDomain.FINANCIAL,
                value=round(exposure_ratio * 100.0, 2),
                unit="percent",
                target=round(
                    self._policy.maximum_financial_exposure_ratio
                    * 100.0,
                    2,
                ),
            ),
        )

    def _build_directives(
        self,
        snapshot: EnterpriseCommandSnapshot,
    ) -> tuple[ExecutiveDirective, ...]:
        directives: list[ExecutiveDirective] = []

        if (
            snapshot.blocked_procurements
            >= self._policy.blocked_procurement_critical_count
        ):
            directives.append(
                self._directive(
                    code="CRITICAL_BLOCKED_PROCUREMENTS",
                    title="Critical procurement blockage",
                    rationale=(
                        "Blocked procurements exceed the critical "
                        "portfolio threshold."
                    ),
                    domain=CommandCenterDomain.EXECUTION,
                    priority=CommandCenterPriority.CRITICAL,
                    action=ExecutiveAction.PAUSE_EXECUTION,
                    blocking=True,
                )
            )
        elif (
            snapshot.blocked_procurements
            >= self._policy.blocked_procurement_warning_count
        ):
            directives.append(
                self._directive(
                    code="BLOCKED_PROCUREMENTS_WARNING",
                    title="Investigate blocked procurements",
                    rationale=(
                        "One or more procurements require intervention."
                    ),
                    domain=CommandCenterDomain.EXECUTION,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.INVESTIGATE,
                    blocking=False,
                )
            )

        if (
            snapshot.pending_approvals
            >= self._policy.pending_approval_warning_count
        ):
            directives.append(
                self._directive(
                    code="APPROVAL_BACKLOG",
                    title="Clear approval backlog",
                    rationale=(
                        "Pending approvals may delay procurement execution."
                    ),
                    domain=CommandCenterDomain.EXECUTION,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.REQUEST_APPROVAL,
                )
            )

        if (
            snapshot.critical_risks
            >= self._policy.critical_risk_threshold
        ):
            directives.append(
                self._directive(
                    code="CRITICAL_RISK_EXPOSURE",
                    title="Escalate critical risks",
                    rationale=(
                        "Critical risk exposure requires executive action."
                    ),
                    domain=CommandCenterDomain.RISK,
                    priority=CommandCenterPriority.CRITICAL,
                    action=ExecutiveAction.ESCALATE,
                    blocking=True,
                )
            )

        if (
            snapshot.compensation_cases
            >= self._policy.compensation_case_threshold
        ):
            directives.append(
                self._directive(
                    code="COMPENSATION_CASES_ACTIVE",
                    title="Coordinate compensation cases",
                    rationale=(
                        "Active recovery cases require controlled oversight."
                    ),
                    domain=CommandCenterDomain.EXECUTION,
                    priority=CommandCenterPriority.CRITICAL,
                    action=ExecutiveAction.START_COMPENSATION,
                    blocking=True,
                )
            )

        if (
            snapshot.delayed_shipments
            >= self._policy.delayed_shipment_warning_count
        ):
            directives.append(
                self._directive(
                    code="SHIPMENT_DELAY_BACKLOG",
                    title="Expedite delayed shipments",
                    rationale=(
                        "Shipment delays exceed the portfolio threshold."
                    ),
                    domain=CommandCenterDomain.SHIPMENT,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.EXPEDITE_SHIPMENT,
                )
            )

        if snapshot.low_inventory_items > 0:
            directives.append(
                self._directive(
                    code="LOW_INVENTORY_ITEMS",
                    title="Replenish low inventory",
                    rationale=(
                        "Inventory shortages may affect buyer fulfilment."
                    ),
                    domain=CommandCenterDomain.INVENTORY,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.REPLENISH_INVENTORY,
                )
            )

        if (
            snapshot.average_decision_score
            < self._policy.minimum_decision_score
        ):
            directives.append(
                self._directive(
                    code="LOW_AVERAGE_DECISION_SCORE",
                    title="Review procurement decision quality",
                    rationale=(
                        "Average procurement decision score is below policy."
                    ),
                    domain=CommandCenterDomain.PROCUREMENT,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.INVESTIGATE,
                    blocking=True,
                )
            )

        if (
            snapshot.average_autonomous_confidence
            < self._policy.minimum_autonomous_confidence
        ):
            directives.append(
                self._directive(
                    code="LOW_AUTONOMOUS_CONFIDENCE",
                    title="Reduce autonomous execution",
                    rationale=(
                        "Autonomous confidence is below the approved threshold."
                    ),
                    domain=CommandCenterDomain.AUTONOMY,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.PAUSE_EXECUTION,
                    blocking=True,
                )
            )

        if (
            snapshot.payment_clearance_rate
            < self._policy.minimum_payment_clearance_rate
        ):
            directives.append(
                self._directive(
                    code="LOW_PAYMENT_CLEARANCE_RATE",
                    title="Strengthen payment controls",
                    rationale=(
                        "Buyer payment clearance is below the minimum rate."
                    ),
                    domain=CommandCenterDomain.FINANCIAL,
                    priority=CommandCenterPriority.CRITICAL,
                    action=ExecutiveAction.SECURE_PAYMENT,
                    blocking=True,
                )
            )

        if (
            snapshot.document_completeness_rate
            < self._policy.minimum_document_completeness_rate
        ):
            directives.append(
                self._directive(
                    code="LOW_DOCUMENT_COMPLETENESS",
                    title="Complete procurement documentation",
                    rationale=(
                        "Document completeness is below the policy threshold."
                    ),
                    domain=CommandCenterDomain.COMPLIANCE,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.COMPLETE_DOCUMENTS,
                    blocking=True,
                )
            )

        if (
            snapshot.on_time_shipment_rate
            < self._policy.minimum_on_time_shipment_rate
        ):
            directives.append(
                self._directive(
                    code="LOW_ON_TIME_SHIPMENT_RATE",
                    title="Improve shipment performance",
                    rationale=(
                        "On-time shipment performance is below target."
                    ),
                    domain=CommandCenterDomain.SHIPMENT,
                    priority=CommandCenterPriority.HIGH,
                    action=ExecutiveAction.EXPEDITE_SHIPMENT,
                )
            )

        exposure_ratio = (
            snapshot.financial_exposure / snapshot.procurement_value
            if snapshot.procurement_value > 0
            else 0.0
        )

        if (
            exposure_ratio
            > self._policy.maximum_financial_exposure_ratio
        ):
            directives.append(
                self._directive(
                    code="HIGH_FINANCIAL_EXPOSURE",
                    title="Reduce financial exposure",
                    rationale=(
                        "Financial exposure exceeds the permitted ratio."
                    ),
                    domain=CommandCenterDomain.FINANCIAL,
                    priority=CommandCenterPriority.CRITICAL,
                    action=ExecutiveAction.PAUSE_EXECUTION,
                    blocking=True,
                )
            )

        if snapshot.high_value_opportunities > 0:
            directives.append(
                self._directive(
                    code="HIGH_VALUE_OPPORTUNITIES",
                    title="Prioritise high-value opportunities",
                    rationale=(
                        "Strategic opportunities require executive attention."
                    ),
                    domain=CommandCenterDomain.OPPORTUNITY,
                    priority=CommandCenterPriority.MEDIUM,
                    action=ExecutiveAction.PRIORITISE_OPPORTUNITY,
                )
            )

        if not directives:
            directives.append(
                self._directive(
                    code="COMMAND_CENTER_HEALTHY",
                    title="Portfolio operating normally",
                    rationale=(
                        "No material enterprise exceptions were detected."
                    ),
                    domain=CommandCenterDomain.PROCUREMENT,
                    priority=CommandCenterPriority.LOW,
                    action=ExecutiveAction.NO_ACTION,
                )
            )

        return tuple(
            sorted(
                directives,
                key=lambda item: (
                    self._priority_rank(item.priority),
                    not item.blocking,
                    item.domain.value,
                    item.code,
                ),
            )
        )

    def _directive(
        self,
        *,
        code: str,
        title: str,
        rationale: str,
        domain: CommandCenterDomain,
        priority: CommandCenterPriority,
        action: ExecutiveAction,
        blocking: bool = False,
    ) -> ExecutiveDirective:
        return ExecutiveDirective(
            code=code,
            title=title,
            rationale=rationale,
            domain=domain,
            priority=priority,
            action=action,
            blocking=blocking,
        )

    @staticmethod
    def _calculate_health_score(
        snapshot: EnterpriseCommandSnapshot,
        directives: tuple[ExecutiveDirective, ...],
    ) -> float:
        score = (
            snapshot.average_decision_score * 0.20
            + snapshot.average_autonomous_confidence * 0.15
            + snapshot.payment_clearance_rate * 0.20
            + snapshot.document_completeness_rate * 0.15
            + snapshot.on_time_shipment_rate * 0.15
            + max(
                0.0,
                100.0
                - (
                    snapshot.critical_risks * 20.0
                    + snapshot.blocked_procurements * 5.0
                ),
            )
            * 0.15
        )

        score -= sum(
            {
                CommandCenterPriority.CRITICAL: 12.0,
                CommandCenterPriority.HIGH: 6.0,
                CommandCenterPriority.MEDIUM: 2.0,
                CommandCenterPriority.LOW: 0.0,
            }[directive.priority]
            for directive in directives
            if directive.code != "COMMAND_CENTER_HEALTHY"
        )

        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def _resolve_health(
        health_score: float,
        directives: tuple[ExecutiveDirective, ...],
    ) -> CommandCenterHealth:
        if any(
            directive.priority is CommandCenterPriority.CRITICAL
            and directive.blocking
            for directive in directives
        ):
            return CommandCenterHealth.CRITICAL

        if health_score < 50:
            return CommandCenterHealth.DEGRADED

        if health_score < 75:
            return CommandCenterHealth.WATCH

        return CommandCenterHealth.HEALTHY

    @staticmethod
    def _priority_rank(
        priority: CommandCenterPriority,
    ) -> int:
        return {
            CommandCenterPriority.CRITICAL: 0,
            CommandCenterPriority.HIGH: 1,
            CommandCenterPriority.MEDIUM: 2,
            CommandCenterPriority.LOW: 3,
        }[priority]


_default_enterprise_command_center = EnterpriseCommandCenter()


def get_enterprise_command_center() -> EnterpriseCommandCenter:
    return _default_enterprise_command_center