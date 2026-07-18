"""
Enterprise Monitoring Service.

Continuously evaluates the Dawlat AI Procurement & Global Trade Intelligence
Platform for material changes and publishes typed events through the
Enterprise Event Bus.

Monitoring areas:
- active and blocked procurement workflows;
- quotation expiry;
- shipment delay and overdue arrival;
- buyer payment readiness;
- supplier verification and bank-detail changes;
- certificate expiry signals;
- inventory shortages;
- workflow risk and trust deterioration;
- monitoring failures and stale workflows;
- opportunity changes.

This service is read-only with respect to commercial execution. It may publish
alerts and refresh requests, but it never sends quotations, commits suppliers,
releases funds, issues purchase orders, or instructs shipments automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from repositories.procurement_workflow_repository import (
    ProcurementWorkflowRepository,
)
from services.ai_assistant_service import build_ai_context
from services.event_bus import (
    EventCategory,
    EventPriority,
    EventStatus,
    EnterpriseEventBus,
    get_event_bus,
    publish_event,
)
from services.workflow_manager import (
    EnterpriseWorkflowManager,
    get_workflow_manager,
)


@dataclass(frozen=True)
class MonitoringFinding:
    finding_type: str
    severity: str
    title: str
    description: str
    event_name: str
    category: EventCategory
    priority: EventPriority
    source_record_id: int | str | None = None
    workflow_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


@dataclass
class MonitoringCycleResult:
    cycle_id: str
    started_at: str
    finished_at: str
    workflows_checked: int
    findings_detected: int
    events_published: int
    events_failed: int
    findings: list[MonitoringFinding] = field(default_factory=list)
    published_event_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class EnterpriseMonitoringService:
    """Run one governed monitoring cycle across the platform."""

    def __init__(
        self,
        *,
        repository: ProcurementWorkflowRepository | None = None,
        event_bus: EnterpriseEventBus | None = None,
        workflow_manager: EnterpriseWorkflowManager | None = None,
        quotation_warning_days: int = 7,
        stale_workflow_hours: int = 24,
        certificate_warning_days: int = 30,
    ) -> None:
        if quotation_warning_days < 0:
            raise ValueError(
                "quotation_warning_days cannot be negative."
            )
        if stale_workflow_hours < 1:
            raise ValueError(
                "stale_workflow_hours must be at least 1."
            )
        if certificate_warning_days < 0:
            raise ValueError(
                "certificate_warning_days cannot be negative."
            )

        self._repository = (
            repository or ProcurementWorkflowRepository()
        )
        self._event_bus = event_bus or get_event_bus()
        self._workflow_manager = (
            workflow_manager or get_workflow_manager()
        )
        self._quotation_warning_days = quotation_warning_days
        self._stale_workflow_hours = stale_workflow_hours
        self._certificate_warning_days = (
            certificate_warning_days
        )

    def run_cycle(
        self,
        *,
        actor: str = "Enterprise Monitoring Service",
        workflow_limit: int = 200,
    ) -> MonitoringCycleResult:
        """Run one full monitoring cycle."""

        started_at = _now()
        cycle_id = (
            f"MON-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        findings: list[MonitoringFinding] = []
        errors: list[str] = []

        try:
            due_workflows = (
                self._repository.list_due_for_monitoring(
                    limit=workflow_limit
                )
            )
        except Exception as error:
            due_workflows = []
            errors.append(
                f"Unable to list workflows: {error}"
            )

        try:
            context = build_ai_context(
                limit_per_domain=500
            )
        except Exception as error:
            context = {}
            errors.append(
                f"Unable to build monitoring context: {error}"
            )

        findings.extend(
            self._workflow_findings(due_workflows)
        )
        findings.extend(
            self._quotation_findings(
                context.get("supplier_quotes", [])
            )
        )
        findings.extend(
            self._shipment_findings(
                context.get("shipments", [])
            )
        )
        findings.extend(
            self._buyer_findings(
                context.get("customers", [])
            )
        )
        findings.extend(
            self._supplier_findings(
                context.get("suppliers", [])
            )
        )
        findings.extend(
            self._inventory_findings(
                context.get("inventory", [])
            )
        )
        findings.extend(
            self._opportunity_findings(
                context.get("opportunities", [])
            )
        )
        findings = self._deduplicate_findings(
            findings
        )

        published_event_ids: list[str] = []
        events_failed = 0

        for finding in findings:
            try:
                dispatch = publish_event(
                    finding.event_name,
                    category=finding.category,
                    source=actor,
                    payload={
                        "finding_type": (
                            finding.finding_type
                        ),
                        "severity": finding.severity,
                        "title": finding.title,
                        "description": (
                            finding.description
                        ),
                        "source_record_id": (
                            finding.source_record_id
                        ),
                        **finding.payload,
                    },
                    priority=finding.priority,
                    workflow_id=finding.workflow_id,
                    idempotency_key=(
                        finding.idempotency_key
                        or self._finding_key(
                            cycle_id,
                            finding,
                        )
                    ),
                    metadata={
                        "monitoring_cycle_id": cycle_id,
                        "detected_at": _now(),
                    },
                    actor=actor,
                    dispatch=True,
                )

                published_event_ids.append(
                    dispatch.event_id
                )

                if dispatch.status in {
                    EventStatus.FAILED,
                    EventStatus.DEAD_LETTER,
                }:
                    events_failed += 1

            except Exception as error:
                events_failed += 1
                errors.append(
                    f"{finding.event_name}: {error}"
                )

        try:
            workflow_refresh_results = (
                self._workflow_manager
                .process_due_monitoring(
                    limit=workflow_limit,
                    actor=actor,
                )
            )
        except Exception as error:
            workflow_refresh_results = []
            errors.append(
                f"Unable to request workflow refresh: {error}"
            )

        for item in workflow_refresh_results:
            event_id = item.get("event_id")

            if event_id:
                published_event_ids.append(
                    str(event_id)
                )

            if item.get("status") in {
                EventStatus.FAILED.value,
                EventStatus.DEAD_LETTER.value,
            }:
                events_failed += 1

        finished_at = _now()

        self._publish_cycle_summary(
            cycle_id=cycle_id,
            workflows_checked=len(due_workflows),
            findings_detected=len(findings),
            events_published=len(
                published_event_ids
            ),
            events_failed=events_failed,
            errors=errors,
            actor=actor,
        )

        return MonitoringCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            finished_at=finished_at,
            workflows_checked=len(due_workflows),
            findings_detected=len(findings),
            events_published=len(
                published_event_ids
            ),
            events_failed=events_failed,
            findings=findings,
            published_event_ids=(
                published_event_ids
            ),
            errors=errors,
        )

    def _workflow_findings(
        self,
        workflows: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []
        stale_before = (
            datetime.now()
            - timedelta(
                hours=self._stale_workflow_hours
            )
        )

        for item in workflows:
            workflow_id = item.get("workflow_id")
            status = item.get("status") or ""
            stage = item.get("current_stage") or ""
            updated_at = _parse_datetime(
                item.get("updated_at")
            )

            if status == "Blocked":
                findings.append(
                    MonitoringFinding(
                        finding_type="Workflow Blocked",
                        severity="Critical",
                        title="Blocked procurement workflow",
                        description=(
                            f"{workflow_id} is blocked at "
                            f"{stage} with "
                            f"{item.get('blocker_count', 0)} "
                            "blocking issue(s)."
                        ),
                        event_name="workflow.blocked",
                        category=(
                            EventCategory.WORKFLOW
                        ),
                        priority=(
                            EventPriority.CRITICAL
                        ),
                        source_record_id=workflow_id,
                        workflow_id=workflow_id,
                        payload={
                            "current_stage": stage,
                            "status": status,
                            "blocker_count": (
                                item.get(
                                    "blocker_count",
                                    0,
                                )
                            ),
                        },
                        idempotency_key=(
                            f"monitor:workflow-blocked:"
                            f"{workflow_id}:"
                            f"{item.get('version')}"
                        ),
                    )
                )

            if (
                updated_at
                and updated_at < stale_before
                and status not in {
                    "Completed",
                    "Cancelled",
                }
            ):
                findings.append(
                    MonitoringFinding(
                        finding_type="Stale Workflow",
                        severity="High",
                        title="Workflow requires review",
                        description=(
                            f"{workflow_id} has not changed "
                            f"since {updated_at.isoformat()}."
                        ),
                        event_name=(
                            "workflow.stale.detected"
                        ),
                        category=(
                            EventCategory.MONITORING
                        ),
                        priority=EventPriority.HIGH,
                        source_record_id=workflow_id,
                        workflow_id=workflow_id,
                        payload={
                            "current_stage": stage,
                            "status": status,
                            "updated_at": (
                                updated_at.isoformat()
                            ),
                        },
                        idempotency_key=(
                            f"monitor:workflow-stale:"
                            f"{workflow_id}:"
                            f"{updated_at.strftime('%Y%m%d%H')}"
                        ),
                    )
                )

            if (
                item.get("risk_score", 0) >= 75
            ):
                findings.append(
                    MonitoringFinding(
                        finding_type="Critical Risk",
                        severity="Critical",
                        title="Critical workflow risk",
                        description=(
                            f"{workflow_id} has a risk "
                            f"score of "
                            f"{item.get('risk_score')}/100."
                        ),
                        event_name="risk.critical",
                        category=EventCategory.RISK,
                        priority=(
                            EventPriority.CRITICAL
                        ),
                        source_record_id=workflow_id,
                        workflow_id=workflow_id,
                        payload={
                            "risk_score": item.get(
                                "risk_score"
                            ),
                            "current_stage": stage,
                        },
                        idempotency_key=(
                            f"monitor:risk-critical:"
                            f"{workflow_id}:"
                            f"{item.get('version')}"
                        ),
                    )
                )

            if (
                item.get("trust_score", 0) < 55
            ):
                findings.append(
                    MonitoringFinding(
                        finding_type="Trust Failure",
                        severity="Critical",
                        title="Workflow trust failure",
                        description=(
                            f"{workflow_id} has a trust "
                            f"score of "
                            f"{item.get('trust_score')}/100."
                        ),
                        event_name="trust.failed",
                        category=EventCategory.TRUST,
                        priority=(
                            EventPriority.CRITICAL
                        ),
                        source_record_id=workflow_id,
                        workflow_id=workflow_id,
                        payload={
                            "trust_score": item.get(
                                "trust_score"
                            ),
                            "current_stage": stage,
                        },
                        idempotency_key=(
                            f"monitor:trust-failed:"
                            f"{workflow_id}:"
                            f"{item.get('version')}"
                        ),
                    )
                )

        return findings

    def _quotation_findings(
        self,
        quotes: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []
        today = date.today()

        for item in quotes:
            quote_id = item.get("id")
            expiry = _parse_date(
                item.get(
                    "quotation_valid_until"
                )
                or item.get("valid_until")
            )

            if expiry is None:
                continue

            days_remaining = (
                expiry - today
            ).days
            supplier_name = (
                item.get("supplier_name")
                or "Supplier"
            )

            if days_remaining < 0:
                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "Quotation Expired"
                        ),
                        severity="Critical",
                        title=(
                            "Supplier quotation expired"
                        ),
                        description=(
                            f"{supplier_name} quotation "
                            f"expired "
                            f"{abs(days_remaining)} "
                            "day(s) ago."
                        ),
                        event_name=(
                            "quotation.expired"
                        ),
                        category=(
                            EventCategory.QUOTATION
                        ),
                        priority=(
                            EventPriority.CRITICAL
                        ),
                        source_record_id=quote_id,
                        payload={
                            "supplier_name": (
                                supplier_name
                            ),
                            "expiry_date": (
                                expiry.isoformat()
                            ),
                            "days_remaining": (
                                days_remaining
                            ),
                        },
                        idempotency_key=(
                            f"monitor:quote-expired:"
                            f"{quote_id}:"
                            f"{expiry.isoformat()}"
                        ),
                    )
                )

            elif (
                days_remaining
                <= self._quotation_warning_days
            ):
                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "Quotation Expiring"
                        ),
                        severity="High",
                        title=(
                            "Supplier quotation expiring"
                        ),
                        description=(
                            f"{supplier_name} quotation "
                            f"expires in "
                            f"{days_remaining} day(s)."
                        ),
                        event_name=(
                            "quotation.expiring"
                        ),
                        category=(
                            EventCategory.QUOTATION
                        ),
                        priority=EventPriority.HIGH,
                        source_record_id=quote_id,
                        payload={
                            "supplier_name": (
                                supplier_name
                            ),
                            "expiry_date": (
                                expiry.isoformat()
                            ),
                            "days_remaining": (
                                days_remaining
                            ),
                        },
                        idempotency_key=(
                            f"monitor:quote-expiring:"
                            f"{quote_id}:"
                            f"{expiry.isoformat()}:"
                            f"{days_remaining}"
                        ),
                    )
                )

        return findings

    @staticmethod
    def _shipment_findings(
        shipments: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []
        today = date.today()

        for item in shipments:
            shipment_id = item.get("id")
            reference = (
                item.get("shipment_number")
                or item.get("shipment_reference")
                or f"Shipment {shipment_id}"
            )
            status = (
                item.get("shipment_status")
                or item.get("status")
                or ""
            )
            eta = _parse_date(item.get("eta"))
            terminal = status in {
                "Delivered",
                "Completed",
                "Cancelled",
            }

            delayed = bool(
                status in {
                    "Delayed",
                    "Biosecurity Hold",
                    "Inspection Hold",
                }
                or item.get("delay_reason")
                or _number(
                    item.get("delay_days")
                ) > 0
                or (
                    eta
                    and eta < today
                    and not terminal
                )
            )

            if delayed:
                findings.append(
                    MonitoringFinding(
                        finding_type="Shipment Delay",
                        severity="Critical",
                        title="Shipment requires attention",
description=(
    f"{reference}: "
    f"{item.get('delay_reason') or status or 'Overdue'}."
),
                        event_name="shipment.delayed",
                        category=EventCategory.SHIPMENT,
                        priority=(
                            EventPriority.CRITICAL
                        ),
                        source_record_id=shipment_id,
                        workflow_id=item.get(
                            "workflow_id"
                        ),
                        payload={
                            "shipment_reference": (
                                reference
                            ),
                            "status": status,
                            "eta": (
                                eta.isoformat()
                                if eta
                                else None
                            ),
                            "delay_reason": item.get(
                                "delay_reason"
                            ),
                        },
                        idempotency_key=(
                            f"monitor:shipment-delay:"
                            f"{shipment_id}:"
                            f"{status}:"
                            f"{item.get('delay_days') or 0}"
                        ),
                    )
                )

            if status == "Delivered":
                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "Shipment Delivered"
                        ),
                        severity="Low",
                        title=(
                            "Shipment delivered"
                        ),
                        description=(
                            f"{reference} was delivered."
                        ),
                        event_name=(
                            "shipment.delivered"
                        ),
                        category=(
                            EventCategory.SHIPMENT
                        ),
                        priority=EventPriority.LOW,
                        source_record_id=shipment_id,
                        workflow_id=item.get(
                            "workflow_id"
                        ),
                        payload={
                            "shipment_reference": (
                                reference
                            ),
                            "status": status,
                        },
                        idempotency_key=(
                            f"monitor:shipment-delivered:"
                            f"{shipment_id}"
                        ),
                    )
                )

        return findings

    @staticmethod
    def _buyer_findings(
        customers: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []

        for item in customers:
            customer_id = item.get("id")
            name = (
                item.get("company_name")
                or f"Customer {customer_id}"
            )
            lead_status = (
                item.get("lead_status")
                or ""
            )
            credit_status = (
                item.get("credit_status")
                or ""
            )

            if lead_status == "Accepted" and (
                credit_status not in {
                    "Approved",
                    "Good",
                    "Assessed",
                }
            ):
                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "Buyer Credit Pending"
                        ),
                        severity="High",
                        title=(
                            "Accepted buyer needs "
                            "credit review"
                        ),
                        description=(
                            f"{name} accepted commercial "
                            "terms, but credit status is "
                            f"'{credit_status or 'Not assessed'}'."
                        ),
                        event_name=(
                            "buyer.credit.review.required"
                        ),
                        category=EventCategory.BUYER,
                        priority=EventPriority.HIGH,
                        source_record_id=customer_id,
                        payload={
                            "buyer_name": name,
                            "lead_status": lead_status,
                            "credit_status": (
                                credit_status
                            ),
                        },
                        idempotency_key=(
                            f"monitor:buyer-credit:"
                            f"{customer_id}:"
                            f"{credit_status}"
                        ),
                    )
                )

        return findings

    def _supplier_findings(
        self,
        suppliers: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []
        today = date.today()

        for item in suppliers:
            supplier_id = item.get("id")
            name = (
                item.get("company_name")
                or f"Supplier {supplier_id}"
            )
            verification = (
                item.get("verification_status")
                or "Unverified"
            )

            if verification != "Verified":
                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "Supplier Unverified"
                        ),
                        severity="High",
                        title=(
                            "Supplier verification required"
                        ),
                        description=(
                            f"{name} is marked "
                            f"'{verification}'."
                        ),
                        event_name=(
                            "supplier.verification.required"
                        ),
                        category=(
                            EventCategory.SUPPLIER
                        ),
                        priority=EventPriority.HIGH,
                        source_record_id=supplier_id,
                        payload={
                            "supplier_name": name,
                            "verification_status": (
                                verification
                            ),
                        },
                        idempotency_key=(
                            f"monitor:supplier-unverified:"
                            f"{supplier_id}:"
                            f"{verification}"
                        ),
                    )
                )

            certificate_expiry = _parse_date(
                item.get(
                    "certificate_expiry_date"
                )
            )

            if certificate_expiry:
                days_remaining = (
                    certificate_expiry - today
                ).days

                if days_remaining < 0:
                    severity = "Critical"
                    priority = (
                        EventPriority.CRITICAL
                    )
                    event_name = (
                        "certificate.expired"
                    )
                elif (
                    days_remaining
                    <= self._certificate_warning_days
                ):
                    severity = "High"
                    priority = EventPriority.HIGH
                    event_name = (
                        "certificate.expiring"
                    )
                else:
                    continue

                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "Certificate Expiry"
                        ),
                        severity=severity,
                        title=(
                            "Supplier certificate "
                            "requires attention"
                        ),
                        description=(
                            f"{name} certificate "
                            f"{'expired' if days_remaining < 0 else 'expires'} "
                            f"{abs(days_remaining)} "
                            "day(s) "
                            f"{'ago' if days_remaining < 0 else 'from now'}."
                        ),
                        event_name=event_name,
                        category=(
                            EventCategory.COMPLIANCE
                        ),
                        priority=priority,
                        source_record_id=supplier_id,
                        payload={
                            "supplier_name": name,
                            "expiry_date": (
                                certificate_expiry
                                .isoformat()
                            ),
                            "days_remaining": (
                                days_remaining
                            ),
                        },
                        idempotency_key=(
                            f"monitor:certificate:"
                            f"{supplier_id}:"
                            f"{certificate_expiry.isoformat()}:"
                            f"{event_name}"
                        ),
                    )
                )

        return findings

    @staticmethod
    def _inventory_findings(
        inventory: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []

        for item in inventory:
            inventory_id = item.get("id")
            product_name = (
                item.get("product_name")
                or item.get("sku")
                or f"Inventory {inventory_id}"
            )
            available = (
                _number(
                    item.get("quantity_on_hand")
                )
                - _number(
                    item.get("quantity_reserved")
                )
            )
            reorder_level = _number(
                item.get("reorder_level")
            )

            if available <= reorder_level:
                findings.append(
                    MonitoringFinding(
                        finding_type="Low Inventory",
                        severity="High",
                        title="Inventory reorder review",
                        description=(
                            f"{product_name} available "
                            f"quantity is {available:g}; "
                            f"reorder level is "
                            f"{reorder_level:g}."
                        ),
                        event_name=(
                            "inventory.reorder.required"
                        ),
                        category=(
                            EventCategory.INVENTORY
                        ),
                        priority=EventPriority.HIGH,
                        source_record_id=inventory_id,
                        payload={
                            "product_name": (
                                product_name
                            ),
                            "available_quantity": (
                                available
                            ),
                            "reorder_level": (
                                reorder_level
                            ),
                        },
                        idempotency_key=(
                            f"monitor:inventory:"
                            f"{inventory_id}:"
                            f"{available}:"
                            f"{reorder_level}"
                        ),
                    )
                )

        return findings

    @staticmethod
    def _opportunity_findings(
        opportunities: list[dict[str, Any]],
    ) -> list[MonitoringFinding]:
        findings = []

        for item in opportunities:
            opportunity_id = item.get("id")
            confidence = _number(
                item.get("confidence_score")
            )
            demand = _number(
                item.get("demand_score")
            )
            competition = _number(
                item.get("competition_score")
            )
            margin = _number(
                item.get("expected_margin")
            )

            score = round(
                confidence * 0.35
                + demand * 0.35
                + (100 - competition) * 0.20
                + min(100, margin) * 0.10
            )

            if score >= 80:
                findings.append(
                    MonitoringFinding(
                        finding_type=(
                            "High Value Opportunity"
                        ),
                        severity="High",
                        title=(
                            "High-priority opportunity detected"
                        ),
                        description=(
                            f"{item.get('title') or 'Opportunity'} "
                            f"scored {score}/100."
                        ),
                        event_name=(
                            "opportunity.detected"
                        ),
                        category=(
                            EventCategory.OPPORTUNITY
                        ),
                        priority=EventPriority.HIGH,
                        source_record_id=opportunity_id,
                        payload={
                            "opportunity_id": (
                                opportunity_id
                            ),
                            "title": item.get("title"),
                            "product": (
                                item.get("product")
                            ),
                            "opportunity_score": score,
                            "buyer_company": (
                                item.get(
                                    "buyer_company"
                                )
                            ),
                        },
                        idempotency_key=(
                            f"monitor:opportunity:"
                            f"{opportunity_id}:"
                            f"{score}"
                        ),
                    )
                )

        return findings

    @staticmethod
    def _deduplicate_findings(
        findings: list[MonitoringFinding],
    ) -> list[MonitoringFinding]:
        unique: dict[str, MonitoringFinding] = {}

        for item in findings:
            key = (
                item.idempotency_key
                or (
                    f"{item.event_name}:"
                    f"{item.source_record_id}:"
                    f"{item.workflow_id}"
                )
            )

            current = unique.get(key)

            if current is None or (
                _severity_rank(item.severity)
                > _severity_rank(
                    current.severity
                )
            ):
                unique[key] = item

        return sorted(
            unique.values(),
            key=lambda item: (
                -_severity_rank(item.severity),
                item.event_name,
                str(item.source_record_id),
            ),
        )

    @staticmethod
    def _finding_key(
        cycle_id: str,
        finding: MonitoringFinding,
    ) -> str:
        return (
            f"monitor:{cycle_id}:"
            f"{finding.event_name}:"
            f"{finding.source_record_id}:"
            f"{finding.workflow_id or 'none'}"
        )

    @staticmethod
    def _publish_cycle_summary(
        *,
        cycle_id: str,
        workflows_checked: int,
        findings_detected: int,
        events_published: int,
        events_failed: int,
        errors: list[str],
        actor: str,
    ) -> None:
        severity = (
            EventPriority.HIGH
            if events_failed or errors
            else EventPriority.NORMAL
        )

        publish_event(
            "monitoring.cycle.completed",
            category=EventCategory.MONITORING,
            source=actor,
            payload={
                "cycle_id": cycle_id,
                "workflows_checked": (
                    workflows_checked
                ),
                "findings_detected": (
                    findings_detected
                ),
                "events_published": (
                    events_published
                ),
                "events_failed": events_failed,
                "errors": errors,
            },
            priority=severity,
            idempotency_key=(
                f"monitoring-cycle:{cycle_id}"
            ),
            actor=actor,
            dispatch=True,
        )


def _parse_date(
    value: Any,
) -> date | None:
    if not value:
        return None

    try:
        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    text = str(value)

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _number(
    value: Any,
) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _severity_rank(
    severity: str,
) -> int:
    return {
        "Low": 1,
        "Medium": 2,
        "High": 3,
        "Critical": 4,
    }.get(severity, 0)


def _now() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


_monitoring_service = EnterpriseMonitoringService()


def get_monitoring_service() -> EnterpriseMonitoringService:
    """Return the monitoring service singleton."""

    return _monitoring_service


def run_monitoring_cycle(
    *,
    actor: str = "Enterprise Monitoring Service",
    workflow_limit: int = 200,
) -> MonitoringCycleResult:
    """Run one platform monitoring cycle."""

    return _monitoring_service.run_cycle(
        actor=actor,
        workflow_limit=workflow_limit,
    )