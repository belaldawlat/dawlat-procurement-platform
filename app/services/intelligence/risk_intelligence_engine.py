"""
Enterprise Risk Intelligence Engine.

Deterministic, explainable and auditable risk assessment for the Dawlat AI
Procurement Intelligence Platform.

It evaluates buyer, supplier, commercial, payment, logistics, compliance,
documentation, fraud/cyber, operational and reputation risks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

from models.decision import (
    ApprovalStatus,
    BuyerCommercialCommitment,
    BuyerReadinessStatus,
    EnterpriseDecision,
    PaymentStatus,
    RiskFinding,
    RiskSeverity,
    SupplierCommercialOffer,
)


CATEGORY_WEIGHTS = {
    "Buyer": 15,
    "Supplier": 15,
    "Commercial": 15,
    "Payment": 15,
    "Logistics": 10,
    "Compliance": 10,
    "Documentation": 5,
    "Fraud & Cyber": 5,
    "Operational": 5,
    "Reputation": 5,
}


@dataclass(frozen=True)
class CategoryRiskScore:
    category: str
    score: int
    maximum: int
    severity: RiskSeverity
    finding_count: int
    blocking_count: int


@dataclass
class RiskAssessment:
    overall_score: int
    overall_severity: RiskSeverity
    proceed_recommendation: str
    findings: list[RiskFinding] = field(default_factory=list)
    category_scores: list[CategoryRiskScore] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    confidence_score: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocking_reasons)


class RiskIntelligenceEngine:
    """Evaluate full-deal risk using transparent enterprise rules."""

    def assess(self, decision: EnterpriseDecision) -> RiskAssessment:
        findings: list[RiskFinding] = []
        findings += self._buyer_risks(decision.buyer_commitment)
        findings += self._supplier_risks(decision.supplier_offer)
        findings += self._commercial_risks(decision)
        findings += self._payment_risks(decision)
        findings += self._logistics_risks(decision)
        findings += self._compliance_risks(decision)
        findings += self._documentation_risks(decision)
        findings += self._fraud_and_cyber_risks(decision)
        findings += self._operational_risks(decision)
        findings += self._reputation_risks(decision)
        findings += decision.risks
        findings = self._deduplicate_findings(findings)

        category_scores = self._category_scores(findings)
        overall_score = sum(item.score for item in category_scores)
        overall_severity = self._severity_from_score(overall_score)

        blocking_reasons = [
            item.description
            for item in findings
            if item.blocking or item.severity == RiskSeverity.CRITICAL
        ]

        mitigations = list(
            dict.fromkeys(
                item.mitigation
                for item in findings
                if item.mitigation
            )
        )

        return RiskAssessment(
            overall_score=overall_score,
            overall_severity=overall_severity,
            proceed_recommendation=self._recommendation(
                overall_score,
                blocking_reasons,
            ),
            findings=findings,
            category_scores=category_scores,
            blocking_reasons=blocking_reasons,
            mitigations=mitigations,
            confidence_score=self._confidence_score(decision),
        )

    @staticmethod
    def _buyer_risks(
        buyer: BuyerCommercialCommitment | None,
    ) -> list[RiskFinding]:
        if buyer is None:
            return [
                _risk(
                    "Buyer",
                    RiskSeverity.CRITICAL,
                    "No buyer commitment record is attached.",
                    "Demand may not be genuine or commercially binding.",
                    "Create and verify the buyer commitment before sourcing.",
                    blocking=True,
                    owner_role="Customer Acquisition Manager",
                )
            ]

        findings = []

        if not buyer.identity_verified:
            findings.append(
                _risk(
                    "Buyer",
                    RiskSeverity.CRITICAL,
                    "Buyer identity is not verified.",
                    "Fraud, non-payment and enforcement risk.",
                    "Verify the legal entity and authorised representative.",
                    blocking=True,
                    owner_role="Compliance Manager",
                )
            )

        if not buyer.accepted_in_writing:
            findings.append(
                _risk(
                    "Buyer",
                    RiskSeverity.CRITICAL,
                    "Buyer has not accepted the final quotation in writing.",
                    "The buyer may dispute price, quantity or delivery terms.",
                    "Capture written acceptance of the exact quotation version.",
                    blocking=True,
                    owner_role="Sales Manager",
                )
            )

        if buyer.status != BuyerReadinessStatus.FUNDS_CLEARED:
            findings.append(
                _risk(
                    "Buyer",
                    RiskSeverity.CRITICAL,
                    "Buyer funds are not confirmed as cleared.",
                    "Dawlat may commit funds without secured buyer payment.",
                    "Confirm cleared funds or approved payment security.",
                    blocking=True,
                    owner_role="Finance Approver",
                )
            )

        if not buyer.credit_checked:
            findings.append(
                _risk(
                    "Buyer",
                    RiskSeverity.HIGH,
                    "Buyer credit assessment is incomplete.",
                    "The buyer may fail to pay remaining balances.",
                    "Complete credit and payment-history checks.",
                    owner_role="Finance Approver",
                )
            )

        if not buyer.sanctions_checked:
            findings.append(
                _risk(
                    "Compliance",
                    RiskSeverity.HIGH,
                    "Buyer screening is incomplete.",
                    "Legal, sanctions or reputational exposure may exist.",
                    "Complete sanctions and adverse-media screening.",
                    blocking=True,
                    owner_role="Compliance Manager",
                )
            )

        return findings

    @staticmethod
    def _supplier_risks(
        supplier: SupplierCommercialOffer | None,
    ) -> list[RiskFinding]:
        if supplier is None:
            return [
                _risk(
                    "Supplier",
                    RiskSeverity.HIGH,
                    "No supplier offer is selected.",
                    "Supply feasibility and cost are unconfirmed.",
                    "Obtain and compare verified supplier quotations.",
                    blocking=True,
                    owner_role="Global Sourcing Specialist",
                )
            ]

        findings = []

        if not supplier.supplier_verified:
            findings.append(
                _risk(
                    "Supplier",
                    RiskSeverity.CRITICAL,
                    "Supplier identity and capability are not verified.",
                    "Fraud, non-delivery or quality failure may occur.",
                    "Verify legal identity, factory, capacity and references.",
                    blocking=True,
                    owner_role="Global Sourcing Specialist",
                )
            )

        if not supplier.bank_details_verified:
            findings.append(
                _risk(
                    "Fraud & Cyber",
                    RiskSeverity.CRITICAL,
                    "Supplier bank details are not independently verified.",
                    "Funds may be diverted through impersonation or fraud.",
                    "Verify bank details using an independent trusted channel.",
                    blocking=True,
                    owner_role="Finance Approver",
                )
            )

        if supplier.lead_time_days <= 0:
            findings.append(
                _risk(
                    "Supplier",
                    RiskSeverity.HIGH,
                    "Supplier lead time is not confirmed.",
                    "Delivery feasibility cannot be established.",
                    "Obtain written production and dispatch lead times.",
                    owner_role="Procurement Specialist",
                )
            )

        if not supplier.certificates:
            findings.append(
                _risk(
                    "Compliance",
                    RiskSeverity.HIGH,
                    "No supplier certificates are recorded.",
                    "The product may fail buyer or import requirements.",
                    "Obtain, validate and monitor required certificates.",
                    blocking=True,
                    owner_role="Compliance Manager",
                )
            )

        if _is_expired(supplier.validity_date):
            findings.append(
                _risk(
                    "Commercial",
                    RiskSeverity.HIGH,
                    "Supplier quotation has expired.",
                    "Price and availability may no longer be valid.",
                    "Request an updated signed quotation.",
                    blocking=True,
                    owner_role="Procurement Specialist",
                )
            )

        return findings

    @staticmethod
    def _commercial_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        margin = decision.margin_protection

        if margin is None:
            return [
                _risk(
                    "Commercial",
                    RiskSeverity.CRITICAL,
                    "Margin protection analysis is missing.",
                    "The transaction may generate insufficient or negative profit.",
                    "Complete and approve the full landed-cost calculation.",
                    blocking=True,
                    owner_role="Commercial Manager",
                )
            ]

        findings = []

        if not margin.margin_protected:
            findings.append(
                _risk(
                    "Commercial",
                    RiskSeverity.CRITICAL,
                    "Expected margin is below the approved minimum.",
                    "Dawlat Global may lose profit or absorb unforeseen costs.",
                    "Reprice, renegotiate or stop the transaction.",
                    blocking=True,
                    owner_role="Commercial Manager",
                )
            )

        if margin.contingency <= 0:
            findings.append(
                _risk(
                    "Commercial",
                    RiskSeverity.MEDIUM,
                    "No commercial contingency is included.",
                    "Freight, FX, customs or delay changes may erode margin.",
                    "Add a documented contingency allowance.",
                    owner_role="Cost & Profit Analyst",
                )
            )

        if margin.finance_cost <= 0:
            findings.append(
                _risk(
                    "Commercial",
                    RiskSeverity.LOW,
                    "Finance and payment-processing costs may be omitted.",
                    "Reported margin may be overstated.",
                    "Confirm bank, FX, credit and transaction charges.",
                    owner_role="Cost & Profit Analyst",
                )
            )

        return findings

    @staticmethod
    def _payment_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        if not decision.payment_milestones:
            return [
                _risk(
                    "Payment",
                    RiskSeverity.CRITICAL,
                    "Supplier payment milestones are not defined.",
                    "Payments could be released before evidence or performance.",
                    "Create evidence-based payment milestones.",
                    blocking=True,
                    owner_role="Finance Approver",
                )
            ]

        findings = []

        for milestone in decision.payment_milestones:
            if milestone.amount <= 0:
                findings.append(
                    _risk(
                        "Payment",
                        RiskSeverity.HIGH,
                        f"{milestone.stage.value} amount is invalid.",
                        "The payment schedule may be incomplete or misleading.",
                        "Correct and reapprove the milestone amount.",
                        blocking=True,
                        owner_role="Finance Approver",
                    )
                )

            if not milestone.required_evidence:
                findings.append(
                    _risk(
                        "Payment",
                        RiskSeverity.HIGH,
                        f"{milestone.stage.value} has no required evidence.",
                        "Payment may be released without proof of performance.",
                        "Define mandatory evidence for this milestone.",
                        blocking=True,
                        owner_role="Finance Approver",
                    )
                )

            if milestone.status == PaymentStatus.RELEASED and (
                not milestone.conditions_satisfied
                or milestone.finance_approval != ApprovalStatus.APPROVED
                or milestone.management_approval != ApprovalStatus.APPROVED
            ):
                findings.append(
                    _risk(
                        "Payment",
                        RiskSeverity.CRITICAL,
                        f"{milestone.stage.value} was released without all controls.",
                        "Financial loss, fraud or audit failure may have occurred.",
                        "Place the deal on hold and investigate immediately.",
                        blocking=True,
                        owner_role="Managing Director",
                    )
                )

        return findings

    @staticmethod
    def _logistics_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        findings = []
        metadata = decision.metadata

        if not metadata.get("logistics_confirmed", False):
            findings.append(
                _risk(
                    "Logistics",
                    RiskSeverity.HIGH,
                    "Logistics route and capacity are not confirmed.",
                    "The delivery date and total cost may fail.",
                    "Obtain a valid freight quotation and booking plan.",
                    owner_role="Logistics Coordinator",
                )
            )

        if metadata.get("shipment_delayed", False):
            findings.append(
                _risk(
                    "Logistics",
                    RiskSeverity.HIGH,
                    "A related shipment is delayed or on hold.",
                    "Buyer delivery and trust may be affected.",
                    "Create a recovery plan and notify authorised stakeholders.",
                    owner_role="Logistics Coordinator",
                )
            )

        return findings

    @staticmethod
    def _compliance_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        findings = []
        metadata = decision.metadata

        if not metadata.get("import_requirements_verified", False):
            findings.append(
                _risk(
                    "Compliance",
                    RiskSeverity.HIGH,
                    "Import and biosecurity requirements are not verified.",
                    "Cargo may be delayed, treated, rejected or destroyed.",
                    "Confirm current import, customs and biosecurity requirements.",
                    blocking=True,
                    owner_role="Compliance Manager",
                )
            )

        if metadata.get("certificate_expiry_detected", False):
            findings.append(
                _risk(
                    "Compliance",
                    RiskSeverity.CRITICAL,
                    "A required certificate is expired or near expiry.",
                    "The product may be non-compliant.",
                    "Obtain and independently verify a valid certificate.",
                    blocking=True,
                    owner_role="Compliance Manager",
                )
            )

        return findings

    @staticmethod
    def _documentation_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        if decision.evidence:
            return []

        return [
            _risk(
                "Documentation",
                RiskSeverity.HIGH,
                "No supporting evidence is attached to the decision.",
                "The recommendation cannot be independently verified or audited.",
                "Attach source records, quotations, contracts and verification evidence.",
                blocking=True,
                owner_role="Documentation Specialist",
            )
        ]

    @staticmethod
    def _fraud_and_cyber_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        findings = []
        metadata = decision.metadata

        checks = (
            (
                "bank_details_changed",
                "Supplier bank details changed during the transaction.",
                "Business-email-compromise or payment diversion may be occurring.",
                "Freeze payment and reverify using known independent contacts.",
            ),
            (
                "email_domain_mismatch",
                "Email domain does not match the verified company domain.",
                "Impersonation or phishing may be occurring.",
                "Stop communication and verify the sender independently.",
            ),
            (
                "duplicate_invoice_detected",
                "A possible duplicate invoice was detected.",
                "Duplicate or fraudulent payment may occur.",
                "Block payment and reconcile invoice references.",
            ),
        )

        for key, description, impact, mitigation in checks:
            if metadata.get(key, False):
                findings.append(
                    _risk(
                        "Fraud & Cyber",
                        RiskSeverity.CRITICAL,
                        description,
                        impact,
                        mitigation,
                        blocking=True,
                        owner_role="Finance Approver",
                    )
                )

        return findings

    @staticmethod
    def _operational_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        findings = []

        if any(
            item.status == ApprovalStatus.REJECTED
            for item in decision.approvals
        ):
            findings.append(
                _risk(
                    "Operational",
                    RiskSeverity.CRITICAL,
                    "A mandatory approval was rejected.",
                    "The transaction is not authorised.",
                    "Resolve the rejection before proceeding.",
                    blocking=True,
                    owner_role="Managing Director",
                )
            )

        if any(
            item.status in {
                ApprovalStatus.EXPIRED,
                ApprovalStatus.REVOKED,
            }
            for item in decision.approvals
        ):
            findings.append(
                _risk(
                    "Operational",
                    RiskSeverity.HIGH,
                    "A required approval is expired or revoked.",
                    "The decision may no longer be valid.",
                    "Request a new authorised approval.",
                    blocking=True,
                    owner_role="Managing Director",
                )
            )

        if decision.data_gaps:
            findings.append(
                _risk(
                    "Operational",
                    RiskSeverity.MEDIUM,
                    f"{len(decision.data_gaps)} material data gap(s) remain.",
                    "Decision confidence may be overstated.",
                    "Resolve all material data gaps before approval.",
                    owner_role="Executive Advisor",
                )
            )

        return findings

    @staticmethod
    def _reputation_risks(
        decision: EnterpriseDecision,
    ) -> list[RiskFinding]:
        if not decision.metadata.get(
            "relationship_bypass_risk",
            False,
        ):
            return []

        return [
            _risk(
                "Reputation",
                RiskSeverity.HIGH,
                "Buyer or supplier bypass risk is detected.",
                "Dawlat Global may lose margin, trust and the relationship.",
                "Use confidentiality, non-circumvention and controlled communication.",
                owner_role="Commercial Manager",
            )
        ]

    @staticmethod
    def _category_scores(
        findings: list[RiskFinding],
    ) -> list[CategoryRiskScore]:
        grouped = {
            category: []
            for category in CATEGORY_WEIGHTS
        }

        for finding in findings:
            category = (
                finding.category
                if finding.category in grouped
                else "Operational"
            )
            grouped[category].append(finding)

        result = []

        for category, maximum in CATEGORY_WEIGHTS.items():
            items = grouped[category]
            raw = sum(
                {
                    RiskSeverity.LOW: 2,
                    RiskSeverity.MEDIUM: 5,
                    RiskSeverity.HIGH: 9,
                    RiskSeverity.CRITICAL: 15,
                }[item.severity]
                for item in items
            )
            score = min(maximum, raw)

            result.append(
                CategoryRiskScore(
                    category=category,
                    score=score,
                    maximum=maximum,
                    severity=RiskIntelligenceEngine._severity_from_ratio(
                        score,
                        maximum,
                    ),
                    finding_count=len(items),
                    blocking_count=sum(
                        1
                        for item in items
                        if item.blocking
                    ),
                )
            )

        return result

    @staticmethod
    def _severity_from_ratio(
        score: int,
        maximum: int,
    ) -> RiskSeverity:
        ratio = score / maximum if maximum else 0

        if ratio >= 0.75:
            return RiskSeverity.CRITICAL
        if ratio >= 0.5:
            return RiskSeverity.HIGH
        if ratio >= 0.25:
            return RiskSeverity.MEDIUM
        return RiskSeverity.LOW

    @staticmethod
    def _severity_from_score(
        score: int,
    ) -> RiskSeverity:
        if score >= 75:
            return RiskSeverity.CRITICAL
        if score >= 50:
            return RiskSeverity.HIGH
        if score >= 25:
            return RiskSeverity.MEDIUM
        return RiskSeverity.LOW

    @staticmethod
    def _recommendation(
        overall_score: int,
        blocking_reasons: list[str],
    ) -> str:
        if blocking_reasons:
            return "BLOCK — resolve all mandatory controls first."
        if overall_score >= 50:
            return "HOLD — senior management review required."
        if overall_score >= 25:
            return "PROCEED CONDITIONALLY — complete mitigations first."
        return "PROCEED — continue through normal approval controls."

    @staticmethod
    def _confidence_score(
        decision: EnterpriseDecision,
    ) -> int:
        score = decision.confidence_score
        score += min(10, len(decision.evidence) * 2)
        score -= min(30, len(decision.data_gaps) * 5)
        return max(0, min(100, score))

    @staticmethod
    def _deduplicate_findings(
        findings: Iterable[RiskFinding],
    ) -> list[RiskFinding]:
        unique = {}

        for item in findings:
            key = (
                item.category,
                item.severity.value,
                item.description.strip().lower(),
            )
            unique[key] = item

        return list(unique.values())


def _risk(
    category: str,
    severity: RiskSeverity,
    description: str,
    impact: str,
    mitigation: str,
    *,
    blocking: bool = False,
    owner_role: str = "",
) -> RiskFinding:
    return RiskFinding(
        category=category,
        severity=severity,
        description=description,
        impact=impact,
        mitigation=mitigation,
        blocking=blocking,
        owner_role=owner_role,
    )


def _is_expired(value: str | None) -> bool:
    if not value:
        return False

    try:
        return date.fromisoformat(value) < date.today()
    except ValueError:
        return False


_engine = RiskIntelligenceEngine()


def assess_enterprise_risk(
    decision: EnterpriseDecision,
) -> RiskAssessment:
    """Public risk-assessment entry point."""

    return _engine.assess(decision)