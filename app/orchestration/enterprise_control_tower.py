"""Enterprise control tower for procurement operations."""

from __future__ import annotations

from app.orchestration.enterprise_control_models import (
    ControlAction,
    ControlDomain,
    ControlHealth,
    ControlPriority,
    EnterpriseControlAlert,
    EnterpriseControlMetric,
    EnterpriseControlSnapshot,
)
from app.orchestration.enterprise_control_policy import (
    EnterpriseControlPolicy,
)
from app.orchestration.enterprise_control_result import (
    EnterpriseControlResult,
)


class EnterpriseControlTower:
    """Evaluate operational health and generate control alerts."""

    def __init__(
        self,
        policy: EnterpriseControlPolicy | None = None,
    ) -> None:
        self._policy = policy or EnterpriseControlPolicy(
            policy_id="default-enterprise-control",
            name="Default Enterprise Control Policy",
        )

    @property
    def policy(self) -> EnterpriseControlPolicy:
        """Return the active control policy."""

        return self._policy

    def evaluate(
        self,
        snapshot: EnterpriseControlSnapshot,
    ) -> EnterpriseControlResult:
        """Evaluate an enterprise control snapshot."""

        if not isinstance(snapshot, EnterpriseControlSnapshot):
            raise TypeError(
                "Control tower requires an EnterpriseControlSnapshot."
            )

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise control policy is disabled."
            )

        metrics = self._build_metrics(snapshot)
        alerts = self._build_alerts(snapshot)
        health_score = self._calculate_health_score(
            snapshot,
            alerts,
        )
        health = self._resolve_health(
            health_score,
            alerts,
        )
        execution_blocked = any(
            alert.blocking
            for alert in alerts
        )

        return EnterpriseControlResult(
            case_id=snapshot.case_id,
            health=health,
            health_score=health_score,
            metrics=metrics,
            alerts=alerts,
            execution_blocked=execution_blocked,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "procurement_status": snapshot.procurement_status,
                "alert_count": len(alerts),
                "metric_count": len(metrics),
            },
        )

    def _build_metrics(
        self,
        snapshot: EnterpriseControlSnapshot,
    ) -> tuple[EnterpriseControlMetric, ...]:
        """Build deterministic operational metrics."""

        metrics = [
            EnterpriseControlMetric(
                metric_id="decision-score",
                name="Decision Score",
                domain=ControlDomain.PROCUREMENT,
                value=snapshot.decision_score,
                unit="score",
                target=self._policy.minimum_decision_score,
                warning_threshold=self._policy.minimum_decision_score,
                higher_is_better=True,
            ),
            EnterpriseControlMetric(
                metric_id="autonomous-confidence",
                name="Autonomous Confidence",
                domain=ControlDomain.AUTONOMY,
                value=snapshot.autonomous_confidence,
                unit="score",
                target=self._policy.minimum_autonomous_confidence,
                warning_threshold=(
                    self._policy.minimum_autonomous_confidence
                ),
                higher_is_better=True,
            ),
            EnterpriseControlMetric(
                metric_id="supplier-risk",
                name="Supplier Risk",
                domain=ControlDomain.RISK,
                value=snapshot.supplier_risk_score,
                unit="score",
                warning_threshold=(
                    self._policy.maximum_supplier_risk_score
                ),
                critical_threshold=(
                    self._policy.critical_supplier_risk_score
                ),
                higher_is_better=False,
            ),
            EnterpriseControlMetric(
                metric_id="shipment-delay",
                name="Shipment Delay",
                domain=ControlDomain.SHIPMENT,
                value=float(snapshot.shipment_delay_days),
                unit="days",
                warning_threshold=float(
                    self._policy.shipment_delay_warning_days
                ),
                critical_threshold=float(
                    self._policy.shipment_delay_critical_days
                ),
                higher_is_better=False,
            ),
            EnterpriseControlMetric(
                metric_id="opportunity-score",
                name="Opportunity Score",
                domain=ControlDomain.OPPORTUNITY,
                value=snapshot.opportunity_score,
                unit="score",
                target=self._policy.high_opportunity_score,
                higher_is_better=True,
            ),
        ]

        if snapshot.inventory_days_remaining is not None:
            metrics.append(
                EnterpriseControlMetric(
                    metric_id="inventory-coverage",
                    name="Inventory Coverage",
                    domain=ControlDomain.INVENTORY,
                    value=snapshot.inventory_days_remaining,
                    unit="days",
                    warning_threshold=(
                        self._policy.low_inventory_warning_days
                    ),
                    critical_threshold=(
                        self._policy.low_inventory_critical_days
                    ),
                    higher_is_better=True,
                )
            )

        return tuple(metrics)

    def _build_alerts(
        self,
        snapshot: EnterpriseControlSnapshot,
    ) -> tuple[EnterpriseControlAlert, ...]:
        """Build prioritised enterprise alerts."""

        alerts: list[EnterpriseControlAlert] = []

        if (
            self._policy.fail_closed_on_missing_payment
            and not snapshot.buyer_payment_cleared
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="BUYER_PAYMENT_NOT_CLEARED",
                    title="Buyer payment not cleared",
                    message=(
                        "Supplier commitment must remain blocked "
                        "until buyer funds are cleared."
                    ),
                    domain=ControlDomain.FINANCIAL,
                    priority=ControlPriority.CRITICAL,
                    action=ControlAction.SECURE_PAYMENT,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if (
            self._policy.fail_closed_on_missing_documents
            and not snapshot.documents_complete
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="DOCUMENTS_INCOMPLETE",
                    title="Required documents incomplete",
                    message=(
                        "Mandatory procurement or compliance "
                        "documents require completion."
                    ),
                    domain=ControlDomain.COMPLIANCE,
                    priority=ControlPriority.HIGH,
                    action=ControlAction.COMPLETE_DOCUMENTS,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if (
            self._policy.fail_closed_on_compensation_required
            and snapshot.compensation_required
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="COMPENSATION_REQUIRED",
                    title="Compensation workflow required",
                    message=(
                        "Execution recovery or rollback must be "
                        "coordinated before proceeding."
                    ),
                    domain=ControlDomain.EXECUTION,
                    priority=ControlPriority.CRITICAL,
                    action=ControlAction.START_COMPENSATION,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if not snapshot.approval_satisfied:
            alerts.append(
                EnterpriseControlAlert(
                    code="APPROVAL_PENDING",
                    title="Commercial approval pending",
                    message=(
                        "Required approval gates have not been satisfied."
                    ),
                    domain=ControlDomain.APPROVAL,
                    priority=ControlPriority.HIGH,
                    action=ControlAction.REQUEST_APPROVAL,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if not snapshot.execution_allowed:
            alerts.append(
                EnterpriseControlAlert(
                    code="EXECUTION_NOT_ALLOWED",
                    title="Execution is not authorised",
                    message=(
                        "Enterprise orchestration has not authorised "
                        "controlled execution."
                    ),
                    domain=ControlDomain.EXECUTION,
                    priority=ControlPriority.HIGH,
                    action=ControlAction.PAUSE_EXECUTION,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if (
            snapshot.decision_score
            < self._policy.minimum_decision_score
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="LOW_DECISION_SCORE",
                    title="Decision score below threshold",
                    message=(
                        "Procurement decision confidence requires review."
                    ),
                    domain=ControlDomain.PROCUREMENT,
                    priority=ControlPriority.HIGH,
                    action=ControlAction.INVESTIGATE,
                    blocking=True,
                    entity_id=snapshot.case_id,
                    metadata={
                        "score": snapshot.decision_score,
                        "minimum": (
                            self._policy.minimum_decision_score
                        ),
                    },
                )
            )

        if (
            snapshot.autonomous_confidence
            < self._policy.minimum_autonomous_confidence
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="LOW_AUTONOMOUS_CONFIDENCE",
                    title="Autonomous confidence below threshold",
                    message=(
                        "Human review is required before autonomous "
                        "execution."
                    ),
                    domain=ControlDomain.AUTONOMY,
                    priority=ControlPriority.HIGH,
                    action=ControlAction.INVESTIGATE,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if (
            snapshot.supplier_risk_score
            >= self._policy.critical_supplier_risk_score
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="CRITICAL_SUPPLIER_RISK",
                    title="Critical supplier risk",
                    message=(
                        "Supplier exposure exceeds the critical "
                        "enterprise threshold."
                    ),
                    domain=ControlDomain.RISK,
                    priority=ControlPriority.CRITICAL,
                    action=ControlAction.ESCALATE,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )
        elif (
            snapshot.supplier_risk_score
            > self._policy.maximum_supplier_risk_score
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="HIGH_SUPPLIER_RISK",
                    title="Supplier risk above threshold",
                    message=(
                        "Supplier risk requires review before execution."
                    ),
                    domain=ControlDomain.RISK,
                    priority=ControlPriority.HIGH,
                    action=ControlAction.INVESTIGATE,
                    blocking=True,
                    entity_id=snapshot.case_id,
                )
            )

        if (
            snapshot.shipment_delay_days
            >= self._policy.shipment_delay_critical_days
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="CRITICAL_SHIPMENT_DELAY",
                    title="Critical shipment delay",
                    message=(
                        "Shipment delay requires immediate escalation."
                    ),
                    domain=ControlDomain.SHIPMENT,
                    priority=ControlPriority.CRITICAL,
                    action=ControlAction.EXPEDITE_SHIPMENT,
                    blocking=False,
                    entity_id=snapshot.case_id,
                )
            )
        elif (
            snapshot.shipment_delay_days
            >= self._policy.shipment_delay_warning_days
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="SHIPMENT_DELAY_WARNING",
                    title="Shipment delay warning",
                    message=(
                        "Shipment progress should be investigated."
                    ),
                    domain=ControlDomain.SHIPMENT,
                    priority=ControlPriority.MEDIUM,
                    action=ControlAction.INVESTIGATE,
                    entity_id=snapshot.case_id,
                )
            )

        if snapshot.inventory_days_remaining is not None:
            if (
                snapshot.inventory_days_remaining
                <= self._policy.low_inventory_critical_days
            ):
                alerts.append(
                    EnterpriseControlAlert(
                        code="CRITICAL_INVENTORY_COVERAGE",
                        title="Critical inventory coverage",
                        message=(
                            "Inventory coverage is below the critical "
                            "operating threshold."
                        ),
                        domain=ControlDomain.INVENTORY,
                        priority=ControlPriority.CRITICAL,
                        action=ControlAction.REPLENISH_INVENTORY,
                        entity_id=snapshot.case_id,
                    )
                )
            elif (
                snapshot.inventory_days_remaining
                <= self._policy.low_inventory_warning_days
            ):
                alerts.append(
                    EnterpriseControlAlert(
                        code="LOW_INVENTORY_COVERAGE",
                        title="Low inventory coverage",
                        message=(
                            "Inventory replenishment should be planned."
                        ),
                        domain=ControlDomain.INVENTORY,
                        priority=ControlPriority.HIGH,
                        action=ControlAction.REPLENISH_INVENTORY,
                        entity_id=snapshot.case_id,
                    )
                )

        if (
            snapshot.opportunity_score
            >= self._policy.high_opportunity_score
            and (
                snapshot.margin_percentage is None
                or snapshot.margin_percentage
                >= self._policy.minimum_margin_percentage
            )
        ):
            alerts.append(
                EnterpriseControlAlert(
                    code="HIGH_VALUE_OPPORTUNITY",
                    title="High-value procurement opportunity",
                    message=(
                        "Opportunity strength and margin justify "
                        "executive attention."
                    ),
                    domain=ControlDomain.OPPORTUNITY,
                    priority=ControlPriority.MEDIUM,
                    action=ControlAction.MONITOR,
                    entity_id=snapshot.case_id,
                    metadata={
                        "opportunity_score": snapshot.opportunity_score,
                        "margin_percentage": snapshot.margin_percentage,
                    },
                )
            )

        if not alerts:
            alerts.append(
                EnterpriseControlAlert(
                    code="CONTROL_TOWER_HEALTHY",
                    title="Operations healthy",
                    message=(
                        "No material enterprise control exceptions "
                        "were detected."
                    ),
                    domain=ControlDomain.PROCUREMENT,
                    priority=ControlPriority.LOW,
                    action=ControlAction.NO_ACTION,
                    entity_id=snapshot.case_id,
                )
            )

        return tuple(
            sorted(
                alerts,
                key=lambda alert: (
                    self._priority_rank(alert.priority),
                    not alert.blocking,
                    alert.domain.value,
                    alert.code,
                ),
            )
        )

    @staticmethod
    def _calculate_health_score(
        snapshot: EnterpriseControlSnapshot,
        alerts: tuple[EnterpriseControlAlert, ...],
    ) -> float:
        """Calculate an explainable enterprise health score."""

        score = (
            snapshot.decision_score * 0.35
            + snapshot.autonomous_confidence * 0.25
            + (100.0 - snapshot.supplier_risk_score) * 0.20
            + (100.0 if snapshot.buyer_payment_cleared else 0.0)
            * 0.10
            + (100.0 if snapshot.documents_complete else 0.0)
            * 0.10
        )

        score -= sum(
            {
                ControlPriority.CRITICAL: 15.0,
                ControlPriority.HIGH: 8.0,
                ControlPriority.MEDIUM: 3.0,
                ControlPriority.LOW: 0.0,
            }[alert.priority]
            for alert in alerts
            if alert.code != "CONTROL_TOWER_HEALTHY"
        )

        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def _resolve_health(
        health_score: float,
        alerts: tuple[EnterpriseControlAlert, ...],
    ) -> ControlHealth:
        """Resolve enterprise health from score and alerts."""

        if any(
            alert.priority is ControlPriority.CRITICAL
            and alert.blocking
            for alert in alerts
        ):
            return ControlHealth.CRITICAL

        if health_score < 50:
            return ControlHealth.AT_RISK

        if health_score < 75:
            return ControlHealth.DEGRADED

        return ControlHealth.HEALTHY

    @staticmethod
    def _priority_rank(
        priority: ControlPriority,
    ) -> int:
        return {
            ControlPriority.CRITICAL: 0,
            ControlPriority.HIGH: 1,
            ControlPriority.MEDIUM: 2,
            ControlPriority.LOW: 3,
        }[priority]


_default_enterprise_control_tower = EnterpriseControlTower()


def get_enterprise_control_tower() -> EnterpriseControlTower:
    """Return the shared enterprise control tower."""

    return _default_enterprise_control_tower