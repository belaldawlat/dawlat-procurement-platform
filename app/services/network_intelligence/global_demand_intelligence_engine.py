"""
Global Demand Intelligence Engine.

Core demand-side component of the Global Procurement Network Intelligence
(GPNI) subsystem for the Dawlat AI Procurement & Global Trade Intelligence
Platform.

Responsibilities:
- capture and normalize buyer demand from structured and unstructured sources;
- distinguish weak market signals from verified commercial demand;
- score demand quality, urgency, confidence and commercial readiness;
- verify buyer identity, product requirements and evidence;
- identify missing information before supplier matching begins;
- persist demand records, evidence, status history and audit activity;
- expose safe decision outputs to matching and orchestration engines;
- prevent binding supplier activity until buyer and commercial safeguards pass.

This engine does not:
- promise supply;
- contact suppliers automatically;
- issue quotations;
- accept buyer money;
- release supplier payments;
- create purchase orders;
- approve contracts;
- instruct shipments.

All binding or financial actions remain subject to human approval, cleared funds,
verified documents, compliance controls and workflow safeguards.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from database.connection import get_connection


class DemandSourceType(str, Enum):
    DIRECT_BUYER_REQUEST = "Direct Buyer Request"
    SALES_CONVERSATION = "Sales Conversation"
    WEBSITE_ENQUIRY = "Website Enquiry"
    EMAIL = "Email"
    PHONE = "Phone"
    WHATSAPP = "WhatsApp"
    GOVERNMENT_TENDER = "Government Tender"
    PUBLIC_TENDER = "Public Tender"
    MARKETPLACE = "Marketplace"
    DISTRIBUTOR_SIGNAL = "Distributor Signal"
    RETAILER_SIGNAL = "Retailer Signal"
    WHOLESALER_SIGNAL = "Wholesaler Signal"
    IMPORT_DATA = "Import Data"
    MARKET_RESEARCH = "Market Research"
    WEB_DISCOVERY = "Web Discovery"
    PARTNER_REFERRAL = "Partner Referral"
    MANUAL_ENTRY = "Manual Entry"
    OTHER = "Other"


class DemandStatus(str, Enum):
    NEW = "New"
    UNDER_REVIEW = "Under Review"
    NEEDS_INFORMATION = "Needs Information"
    QUALIFIED = "Qualified"
    VERIFIED = "Verified"
    READY_FOR_MATCHING = "Ready for Matching"
    MATCHING_IN_PROGRESS = "Matching in Progress"
    QUOTATION_PREPARATION = "Quotation Preparation"
    BUYER_REVIEW = "Buyer Review"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"
    FULFILLED = "Fulfilled"


class BuyerReadiness(str, Enum):
    UNKNOWN = "Unknown"
    EARLY_INTEREST = "Early Interest"
    REQUIREMENT_CONFIRMED = "Requirement Confirmed"
    BUDGET_CONFIRMED = "Budget Confirmed"
    DECISION_MAKER_CONFIRMED = "Decision Maker Confirmed"
    COMMERCIAL_REVIEW = "Commercial Review"
    READY_TO_BUY = "Ready to Buy"
    PURCHASE_APPROVED = "Purchase Approved"


class PaymentReadiness(str, Enum):
    UNKNOWN = "Unknown"
    NOT_DISCLOSED = "Not Disclosed"
    SUBJECT_TO_APPROVAL = "Subject to Approval"
    CREDIT_REVIEW_REQUIRED = "Credit Review Required"
    DEPOSIT_READY = "Deposit Ready"
    FULL_PAYMENT_READY = "Full Payment Ready"
    FUNDS_CLEARED = "Funds Cleared"


class VerificationStatus(str, Enum):
    UNVERIFIED = "Unverified"
    PARTIALLY_VERIFIED = "Partially Verified"
    VERIFIED = "Verified"
    FAILED = "Failed"


class DemandPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class EvidenceType(str, Enum):
    BUYER_EMAIL = "Buyer Email"
    SIGNED_REQUIREMENT = "Signed Requirement"
    PURCHASE_REQUEST = "Purchase Request"
    TENDER_DOCUMENT = "Tender Document"
    WEBSITE_SOURCE = "Website Source"
    COMPANY_REGISTRATION = "Company Registration"
    BUYER_IDENTITY = "Buyer Identity"
    PRODUCT_SPECIFICATION = "Product Specification"
    QUANTITY_CONFIRMATION = "Quantity Confirmation"
    TARGET_PRICE = "Target Price"
    DELIVERY_REQUIREMENT = "Delivery Requirement"
    PAYMENT_CONFIRMATION = "Payment Confirmation"
    CREDIT_ASSESSMENT = "Credit Assessment"
    MEETING_NOTE = "Meeting Note"
    CALL_NOTE = "Call Note"
    MARKET_SIGNAL = "Market Signal"
    OTHER = "Other"


@dataclass(frozen=True)
class DemandEvidence:
    evidence_id: str
    evidence_type: EvidenceType
    title: str
    summary: str
    source_reference: str
    source_url: str | None = None
    document_reference: str | None = None
    verified: bool = False
    confidence_score: int = 50
    observed_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BuyerIdentity:
    buyer_id: str | None
    company_name: str
    buyer_type: str
    country: str
    city: str | None = None
    contact_name: str | None = None
    contact_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    registration_number: str | None = None
    tax_number: str | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    credit_status: str | None = None


@dataclass(frozen=True)
class ProductRequirement:
    product_name: str
    category: str | None = None
    specification: str | None = None
    quality_grade: str | None = None
    brand_requirement: str | None = None
    packaging: str | None = None
    private_label_required: bool = False
    quantity: float | None = None
    unit: str | None = None
    repeat_frequency: str | None = None
    target_price: float | None = None
    currency: str = "AUD"
    preferred_incoterm: str | None = None
    destination_country: str = "Australia"
    destination_city: str | None = None
    destination_port: str | None = None
    required_by_date: str | None = None
    certificates_required: tuple[str, ...] = ()
    compliance_requirements: tuple[str, ...] = ()
    sample_required: bool = False


@dataclass(frozen=True)
class DemandCandidate:
    demand_id: str
    title: str
    buyer: BuyerIdentity
    requirement: ProductRequirement
    source_type: DemandSourceType
    source_reference: str
    source_url: str | None = None
    buyer_readiness: BuyerReadiness = BuyerReadiness.UNKNOWN
    payment_readiness: PaymentReadiness = PaymentReadiness.UNKNOWN
    status: DemandStatus = DemandStatus.NEW
    evidence: tuple[DemandEvidence, ...] = ()
    notes: str = ""
    assigned_owner: str | None = None
    created_by: str = "System"
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DemandAssessment:
    demand_id: str
    overall_score: int
    confidence_score: int
    priority: DemandPriority
    identity_score: int
    requirement_score: int
    commercial_score: int
    evidence_score: int
    urgency_score: int
    buyer_readiness_score: int
    payment_readiness_score: int
    verification_status: VerificationStatus
    recommended_status: DemandStatus
    matching_allowed: bool
    supplier_outreach_allowed: bool
    binding_action_allowed: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    strengths: tuple[str, ...]
    next_actions: tuple[str, ...]
    explanation: str
    assessed_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass
class DemandIntelligenceReport:
    candidate: DemandCandidate
    assessment: DemandAssessment
    created: bool
    evidence_created: int
    audit_reference: str
    warnings: list[str] = field(default_factory=list)


def create_global_demand_tables() -> None:
    """Create GPNI demand persistence tables."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_demand_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demand_id TEXT NOT NULL UNIQUE,
                fingerprint TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                buyer_id TEXT,
                buyer_company TEXT NOT NULL,
                buyer_type TEXT NOT NULL,
                buyer_country TEXT NOT NULL,
                buyer_city TEXT,
                contact_name TEXT,
                contact_role TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                buyer_website TEXT,
                registration_number TEXT,
                tax_number TEXT,
                buyer_verification_status TEXT NOT NULL,
                buyer_credit_status TEXT,
                product_name TEXT NOT NULL,
                product_category TEXT,
                specification TEXT,
                quality_grade TEXT,
                brand_requirement TEXT,
                packaging TEXT,
                private_label_required INTEGER NOT NULL DEFAULT 0,
                quantity REAL,
                unit TEXT,
                repeat_frequency TEXT,
                target_price REAL,
                currency TEXT NOT NULL,
                preferred_incoterm TEXT,
                destination_country TEXT NOT NULL,
                destination_city TEXT,
                destination_port TEXT,
                required_by_date TEXT,
                certificates_required_json TEXT NOT NULL DEFAULT '[]',
                compliance_requirements_json TEXT NOT NULL DEFAULT '[]',
                sample_required INTEGER NOT NULL DEFAULT 0,
                source_type TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                source_url TEXT,
                buyer_readiness TEXT NOT NULL,
                payment_readiness TEXT NOT NULL,
                status TEXT NOT NULL,
                overall_score INTEGER NOT NULL DEFAULT 0,
                confidence_score INTEGER NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'Medium',
                matching_allowed INTEGER NOT NULL DEFAULT 0,
                supplier_outreach_allowed INTEGER NOT NULL DEFAULT 0,
                binding_action_allowed INTEGER NOT NULL DEFAULT 0,
                blockers_json TEXT NOT NULL DEFAULT '[]',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                strengths_json TEXT NOT NULL DEFAULT '[]',
                next_actions_json TEXT NOT NULL DEFAULT '[]',
                explanation TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                assigned_owner TEXT,
                created_by TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_assessed_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_demand_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL UNIQUE,
                demand_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                source_url TEXT,
                document_reference TEXT,
                verified INTEGER NOT NULL DEFAULT 0,
                confidence_score INTEGER NOT NULL DEFAULT 50,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (demand_id)
                    REFERENCES global_demand_records(demand_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_demand_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demand_id TEXT NOT NULL,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                FOREIGN KEY (demand_id)
                    REFERENCES global_demand_records(demand_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_demand_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL UNIQUE,
                demand_id TEXT,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_demand_status
            ON global_demand_records(status, priority, overall_score DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_demand_product
            ON global_demand_records(product_name, destination_country)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_demand_buyer
            ON global_demand_records(buyer_company, buyer_country)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_demand_matching
            ON global_demand_records(
                matching_allowed,
                supplier_outreach_allowed,
                confidence_score DESC
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_demand_evidence
            ON global_demand_evidence(demand_id, verified, confidence_score DESC)
            """
        )

        connection.commit()


class GlobalDemandIntelligenceEngine:
    """Discover, assess, persist and govern global buyer demand."""

    def __init__(self) -> None:
        create_global_demand_tables()

    def ingest(
        self,
        candidate: DemandCandidate,
        *,
        actor: str = "Global Demand Intelligence Engine",
    ) -> DemandIntelligenceReport:
        """Assess and persist one demand candidate."""

        normalized = self.normalize_candidate(candidate)
        assessment = self.assess(normalized)
        fingerprint = self._fingerprint(normalized)

        existing = self._find_by_fingerprint(fingerprint)
        created = existing is None

        previous_status = (
            existing.get("status")
            if existing
            else None
        )

        self._upsert_record(
            normalized,
            assessment,
            fingerprint=fingerprint,
        )

        evidence_created = self._persist_evidence(
            normalized.demand_id,
            normalized.evidence,
        )

        if previous_status != assessment.recommended_status.value:
            self._record_status_change(
                normalized.demand_id,
                previous_status=previous_status,
                new_status=assessment.recommended_status.value,
                reason=assessment.explanation,
                changed_by=actor,
            )

        audit_id = self._audit(
            demand_id=normalized.demand_id,
            action=(
                "Demand Created"
                if created
                else "Demand Updated"
            ),
            actor=actor,
            details={
                "overall_score": assessment.overall_score,
                "confidence_score": assessment.confidence_score,
                "priority": assessment.priority.value,
                "matching_allowed": assessment.matching_allowed,
                "supplier_outreach_allowed": (
                    assessment.supplier_outreach_allowed
                ),
                "binding_action_allowed": (
                    assessment.binding_action_allowed
                ),
                "blockers": list(assessment.blockers),
            },
        )

        return DemandIntelligenceReport(
            candidate=normalized,
            assessment=assessment,
            created=created,
            evidence_created=evidence_created,
            audit_reference=audit_id,
        )

    def assess(
        self,
        candidate: DemandCandidate,
    ) -> DemandAssessment:
        """Produce an explainable governed demand assessment."""

        identity_score = self._identity_score(candidate)
        requirement_score = self._requirement_score(candidate)
        commercial_score = self._commercial_score(candidate)
        evidence_score = self._evidence_score(candidate)
        urgency_score = self._urgency_score(candidate)
        buyer_readiness_score = self._buyer_readiness_score(
            candidate.buyer_readiness
        )
        payment_readiness_score = self._payment_readiness_score(
            candidate.payment_readiness
        )

        weighted_score = round(
            identity_score * 0.18
            + requirement_score * 0.22
            + commercial_score * 0.16
            + evidence_score * 0.18
            + urgency_score * 0.08
            + buyer_readiness_score * 0.10
            + payment_readiness_score * 0.08
        )

        blockers = self._blockers(candidate)
        warnings = self._warnings(candidate)
        strengths = self._strengths(
            candidate,
            identity_score=identity_score,
            requirement_score=requirement_score,
            evidence_score=evidence_score,
        )

        confidence_score = self._confidence_score(
            candidate,
            identity_score=identity_score,
            requirement_score=requirement_score,
            evidence_score=evidence_score,
        )

        verification_status = self._verification_status(
            candidate,
            identity_score=identity_score,
            evidence_score=evidence_score,
        )

        matching_allowed = bool(
            weighted_score >= 65
            and confidence_score >= 60
            and candidate.buyer_readiness
            in {
                BuyerReadiness.REQUIREMENT_CONFIRMED,
                BuyerReadiness.BUDGET_CONFIRMED,
                BuyerReadiness.DECISION_MAKER_CONFIRMED,
                BuyerReadiness.COMMERCIAL_REVIEW,
                BuyerReadiness.READY_TO_BUY,
                BuyerReadiness.PURCHASE_APPROVED,
            }
            and not self._critical_matching_blockers(blockers)
        )

        supplier_outreach_allowed = bool(
            matching_allowed
            and verification_status
            in {
                VerificationStatus.PARTIALLY_VERIFIED,
                VerificationStatus.VERIFIED,
            }
            and candidate.requirement.quantity is not None
            and candidate.requirement.quantity > 0
            and bool(candidate.requirement.specification)
        )

        binding_action_allowed = bool(
            supplier_outreach_allowed
            and verification_status == VerificationStatus.VERIFIED
            and candidate.buyer_readiness
            == BuyerReadiness.PURCHASE_APPROVED
            and candidate.payment_readiness
            == PaymentReadiness.FUNDS_CLEARED
            and not blockers
        )

        recommended_status = self._recommended_status(
            candidate,
            verification_status=verification_status,
            matching_allowed=matching_allowed,
            supplier_outreach_allowed=supplier_outreach_allowed,
            binding_action_allowed=binding_action_allowed,
            blockers=blockers,
        )

        priority = self._priority(
            weighted_score=weighted_score,
            urgency_score=urgency_score,
            buyer_readiness_score=buyer_readiness_score,
            payment_readiness_score=payment_readiness_score,
        )

        next_actions = self._next_actions(
            candidate,
            blockers=blockers,
            verification_status=verification_status,
            matching_allowed=matching_allowed,
            supplier_outreach_allowed=supplier_outreach_allowed,
        )

        explanation = self._explanation(
            candidate,
            weighted_score=weighted_score,
            confidence_score=confidence_score,
            verification_status=verification_status,
            matching_allowed=matching_allowed,
            supplier_outreach_allowed=supplier_outreach_allowed,
            binding_action_allowed=binding_action_allowed,
            blockers=blockers,
        )

        return DemandAssessment(
            demand_id=candidate.demand_id,
            overall_score=max(0, min(100, weighted_score)),
            confidence_score=confidence_score,
            priority=priority,
            identity_score=identity_score,
            requirement_score=requirement_score,
            commercial_score=commercial_score,
            evidence_score=evidence_score,
            urgency_score=urgency_score,
            buyer_readiness_score=buyer_readiness_score,
            payment_readiness_score=payment_readiness_score,
            verification_status=verification_status,
            recommended_status=recommended_status,
            matching_allowed=matching_allowed,
            supplier_outreach_allowed=supplier_outreach_allowed,
            binding_action_allowed=binding_action_allowed,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            strengths=tuple(strengths),
            next_actions=tuple(next_actions),
            explanation=explanation,
        )

    def normalize_candidate(
        self,
        candidate: DemandCandidate,
    ) -> DemandCandidate:
        """Return a cleaned and consistently formatted candidate."""

        buyer = BuyerIdentity(
            buyer_id=_clean_optional(candidate.buyer.buyer_id),
            company_name=_clean_required(
                candidate.buyer.company_name,
                "buyer company name",
            ),
            buyer_type=_clean_required(
                candidate.buyer.buyer_type,
                "buyer type",
            ),
            country=_clean_required(
                candidate.buyer.country,
                "buyer country",
            ),
            city=_clean_optional(candidate.buyer.city),
            contact_name=_clean_optional(
                candidate.buyer.contact_name
            ),
            contact_role=_clean_optional(
                candidate.buyer.contact_role
            ),
            email=_normalize_email(candidate.buyer.email),
            phone=_clean_optional(candidate.buyer.phone),
            website=_normalize_url(candidate.buyer.website),
            registration_number=_clean_optional(
                candidate.buyer.registration_number
            ),
            tax_number=_clean_optional(
                candidate.buyer.tax_number
            ),
            verification_status=(
                candidate.buyer.verification_status
            ),
            credit_status=_clean_optional(
                candidate.buyer.credit_status
            ),
        )

        requirement = ProductRequirement(
            product_name=_clean_required(
                candidate.requirement.product_name,
                "product name",
            ),
            category=_clean_optional(
                candidate.requirement.category
            ),
            specification=_clean_optional(
                candidate.requirement.specification
            ),
            quality_grade=_clean_optional(
                candidate.requirement.quality_grade
            ),
            brand_requirement=_clean_optional(
                candidate.requirement.brand_requirement
            ),
            packaging=_clean_optional(
                candidate.requirement.packaging
            ),
            private_label_required=bool(
                candidate.requirement.private_label_required
            ),
            quantity=_positive_number_or_none(
                candidate.requirement.quantity
            ),
            unit=_clean_optional(
                candidate.requirement.unit
            ),
            repeat_frequency=_clean_optional(
                candidate.requirement.repeat_frequency
            ),
            target_price=_positive_number_or_none(
                candidate.requirement.target_price
            ),
            currency=(
                _clean_optional(
                    candidate.requirement.currency
                )
                or "AUD"
            ).upper(),
            preferred_incoterm=_clean_optional(
                candidate.requirement.preferred_incoterm
            ),
            destination_country=(
                _clean_optional(
                    candidate.requirement.destination_country
                )
                or "Australia"
            ),
            destination_city=_clean_optional(
                candidate.requirement.destination_city
            ),
            destination_port=_clean_optional(
                candidate.requirement.destination_port
            ),
            required_by_date=_normalize_date(
                candidate.requirement.required_by_date
            ),
            certificates_required=tuple(
                _unique_clean_strings(
                    candidate.requirement.certificates_required
                )
            ),
            compliance_requirements=tuple(
                _unique_clean_strings(
                    candidate.requirement.compliance_requirements
                )
            ),
            sample_required=bool(
                candidate.requirement.sample_required
            ),
        )

        evidence = tuple(
            self._normalize_evidence(item)
            for item in candidate.evidence
        )

        demand_id = (
            _clean_optional(candidate.demand_id)
            or self._new_demand_id()
        )

        return DemandCandidate(
            demand_id=demand_id,
            title=(
                _clean_optional(candidate.title)
                or (
                    f"{requirement.product_name} demand — "
                    f"{buyer.company_name}"
                )
            ),
            buyer=buyer,
            requirement=requirement,
            source_type=candidate.source_type,
            source_reference=_clean_required(
                candidate.source_reference,
                "source reference",
            ),
            source_url=_normalize_url(
                candidate.source_url
            ),
            buyer_readiness=candidate.buyer_readiness,
            payment_readiness=candidate.payment_readiness,
            status=candidate.status,
            evidence=evidence,
            notes=_clean_optional(candidate.notes) or "",
            assigned_owner=_clean_optional(
                candidate.assigned_owner
            ),
            created_by=(
                _clean_optional(candidate.created_by)
                or "System"
            ),
            created_at=candidate.created_at,
            metadata=dict(candidate.metadata),
        )

    def get(
        self,
        demand_id: str,
    ) -> dict[str, Any] | None:
        """Return one persisted demand with evidence."""

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM global_demand_records
                WHERE demand_id = ?
                LIMIT 1
                """,
                (demand_id,),
            ).fetchone()

            if row is None:
                return None

            evidence_rows = connection.execute(
                """
                SELECT *
                FROM global_demand_evidence
                WHERE demand_id = ?
                ORDER BY verified DESC, confidence_score DESC, observed_at DESC
                """,
                (demand_id,),
            ).fetchall()

        record = self._decode_record(row)
        record["evidence"] = [
            self._decode_evidence_row(item)
            for item in evidence_rows
        ]
        return record

    def list_demands(
        self,
        *,
        status: DemandStatus | None = None,
        product_name: str | None = None,
        destination_country: str | None = None,
        matching_allowed: bool | None = None,
        minimum_score: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List demand records using governed filters."""

        conditions = ["overall_score >= ?"]
        values: list[Any] = [minimum_score]

        if status:
            conditions.append("status = ?")
            values.append(status.value)

        if product_name:
            conditions.append("product_name LIKE ?")
            values.append(f"%{product_name.strip()}%")

        if destination_country:
            conditions.append("destination_country = ?")
            values.append(destination_country.strip())

        if matching_allowed is not None:
            conditions.append("matching_allowed = ?")
            values.append(1 if matching_allowed else 0)

        values.append(max(1, min(limit, 1000)))

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM global_demand_records
                WHERE {' AND '.join(conditions)}
                ORDER BY
                    CASE priority
                        WHEN 'Critical' THEN 4
                        WHEN 'High' THEN 3
                        WHEN 'Medium' THEN 2
                        ELSE 1
                    END DESC,
                    overall_score DESC,
                    confidence_score DESC,
                    updated_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()

        return [
            self._decode_record(row)
            for row in rows
        ]

    def reassess(
        self,
        demand_id: str,
        *,
        actor: str = "Global Demand Intelligence Engine",
    ) -> DemandAssessment:
        """Reassess a persisted demand after evidence or readiness changes."""

        record = self.get(demand_id)

        if record is None:
            raise LookupError(
                f"Demand '{demand_id}' was not found."
            )

        candidate = self._record_to_candidate(record)
        report = self.ingest(
            candidate,
            actor=actor,
        )
        return report.assessment

    def approve_for_matching(
        self,
        demand_id: str,
        *,
        approved_by: str,
        reason: str,
    ) -> None:
        """
        Record human approval for matching.

        This does not override engine blockers. It only advances an already
        eligible demand into matching.
        """

        record = self.get(demand_id)

        if record is None:
            raise LookupError(
                f"Demand '{demand_id}' was not found."
            )

        if not record["matching_allowed"]:
            raise PermissionError(
                "Demand is not eligible for supplier matching."
            )

        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE global_demand_records
                SET
                    status = ?,
                    assigned_owner = COALESCE(assigned_owner, ?),
                    updated_at = ?
                WHERE demand_id = ?
                """,
                (
                    DemandStatus.MATCHING_IN_PROGRESS.value,
                    approved_by,
                    now,
                    demand_id,
                ),
            )
            connection.commit()

        self._record_status_change(
            demand_id,
            previous_status=record["status"],
            new_status=(
                DemandStatus.MATCHING_IN_PROGRESS.value
            ),
            reason=reason,
            changed_by=approved_by,
        )

        self._audit(
            demand_id=demand_id,
            action="Matching Approved",
            actor=approved_by,
            details={"reason": reason},
        )

    @staticmethod
    def _normalize_evidence(
        evidence: DemandEvidence,
    ) -> DemandEvidence:
        return DemandEvidence(
            evidence_id=(
                _clean_optional(evidence.evidence_id)
                or f"EVD-{uuid4().hex[:16].upper()}"
            ),
            evidence_type=evidence.evidence_type,
            title=_clean_required(
                evidence.title,
                "evidence title",
            ),
            summary=_clean_required(
                evidence.summary,
                "evidence summary",
            ),
            source_reference=_clean_required(
                evidence.source_reference,
                "evidence source reference",
            ),
            source_url=_normalize_url(
                evidence.source_url
            ),
            document_reference=_clean_optional(
                evidence.document_reference
            ),
            verified=bool(evidence.verified),
            confidence_score=max(
                0,
                min(100, int(evidence.confidence_score)),
            ),
            observed_at=evidence.observed_at,
            metadata=dict(evidence.metadata),
        )

    @staticmethod
    def _identity_score(
        candidate: DemandCandidate,
    ) -> int:
        score = 20
        buyer = candidate.buyer

        if buyer.company_name:
            score += 15
        if buyer.country:
            score += 10
        if buyer.contact_name:
            score += 10
        if buyer.contact_role:
            score += 10
        if buyer.email:
            score += 10
        if buyer.phone:
            score += 5
        if buyer.website:
            score += 5
        if buyer.registration_number:
            score += 10
        if buyer.tax_number:
            score += 5

        if (
            buyer.verification_status
            == VerificationStatus.VERIFIED
        ):
            score += 20
        elif (
            buyer.verification_status
            == VerificationStatus.PARTIALLY_VERIFIED
        ):
            score += 10
        elif (
            buyer.verification_status
            == VerificationStatus.FAILED
        ):
            score -= 40

        return max(0, min(100, score))

    @staticmethod
    def _requirement_score(
        candidate: DemandCandidate,
    ) -> int:
        requirement = candidate.requirement
        score = 15

        if requirement.product_name:
            score += 15
        if requirement.specification:
            score += 20
        if (
            requirement.quantity is not None
            and requirement.quantity > 0
        ):
            score += 15
        if requirement.unit:
            score += 5
        if requirement.packaging:
            score += 5
        if requirement.destination_country:
            score += 5
        if (
            requirement.destination_city
            or requirement.destination_port
        ):
            score += 5
        if requirement.required_by_date:
            score += 5
        if requirement.certificates_required:
            score += 5
        if requirement.compliance_requirements:
            score += 5

        return max(0, min(100, score))

    @staticmethod
    def _commercial_score(
        candidate: DemandCandidate,
    ) -> int:
        score = 20
        requirement = candidate.requirement

        if requirement.target_price is not None:
            score += 20
        if requirement.currency:
            score += 5
        if requirement.preferred_incoterm:
            score += 10
        if requirement.repeat_frequency:
            score += 10
        if (
            candidate.buyer.credit_status
            in {"Approved", "Good", "Assessed"}
        ):
            score += 15
        if (
            candidate.payment_readiness
            in {
                PaymentReadiness.DEPOSIT_READY,
                PaymentReadiness.FULL_PAYMENT_READY,
                PaymentReadiness.FUNDS_CLEARED,
            }
        ):
            score += 20

        return max(0, min(100, score))

    @staticmethod
    def _evidence_score(
        candidate: DemandCandidate,
    ) -> int:
        if not candidate.evidence:
            return 10

        weighted = 0.0
        total_weight = 0.0

        for evidence in candidate.evidence:
            weight = 1.5 if evidence.verified else 1.0
            weighted += evidence.confidence_score * weight
            total_weight += weight

        average = weighted / total_weight
        evidence_bonus = min(
            20,
            len(candidate.evidence) * 4,
        )
        verified_bonus = min(
            20,
            sum(
                1
                for item in candidate.evidence
                if item.verified
            )
            * 5,
        )

        return max(
            0,
            min(
                100,
                round(
                    average * 0.60
                    + evidence_bonus
                    + verified_bonus
                ),
            ),
        )

    @staticmethod
    def _urgency_score(
        candidate: DemandCandidate,
    ) -> int:
        required_by = _parse_date(
            candidate.requirement.required_by_date
        )

        if required_by is None:
            return 40

        days_remaining = (
            required_by - date.today()
        ).days

        if days_remaining < 0:
            return 10
        if days_remaining <= 7:
            return 100
        if days_remaining <= 30:
            return 85
        if days_remaining <= 60:
            return 70
        if days_remaining <= 120:
            return 55
        return 35

    @staticmethod
    def _buyer_readiness_score(
        readiness: BuyerReadiness,
    ) -> int:
        return {
            BuyerReadiness.UNKNOWN: 10,
            BuyerReadiness.EARLY_INTEREST: 25,
            BuyerReadiness.REQUIREMENT_CONFIRMED: 50,
            BuyerReadiness.BUDGET_CONFIRMED: 65,
            BuyerReadiness.DECISION_MAKER_CONFIRMED: 75,
            BuyerReadiness.COMMERCIAL_REVIEW: 80,
            BuyerReadiness.READY_TO_BUY: 90,
            BuyerReadiness.PURCHASE_APPROVED: 100,
        }[readiness]

    @staticmethod
    def _payment_readiness_score(
        readiness: PaymentReadiness,
    ) -> int:
        return {
            PaymentReadiness.UNKNOWN: 5,
            PaymentReadiness.NOT_DISCLOSED: 15,
            PaymentReadiness.SUBJECT_TO_APPROVAL: 35,
            PaymentReadiness.CREDIT_REVIEW_REQUIRED: 40,
            PaymentReadiness.DEPOSIT_READY: 70,
            PaymentReadiness.FULL_PAYMENT_READY: 85,
            PaymentReadiness.FUNDS_CLEARED: 100,
        }[readiness]

    @staticmethod
    def _blockers(
        candidate: DemandCandidate,
    ) -> list[str]:
        blockers = []
        buyer = candidate.buyer
        requirement = candidate.requirement

        if (
            buyer.verification_status
            == VerificationStatus.FAILED
        ):
            blockers.append(
                "Buyer verification failed."
            )

        if not buyer.company_name:
            blockers.append(
                "Buyer company identity is missing."
            )

        if not requirement.product_name:
            blockers.append(
                "Required product is missing."
            )

        if not requirement.specification:
            blockers.append(
                "Product specification is not confirmed."
            )

        if (
            requirement.quantity is None
            or requirement.quantity <= 0
        ):
            blockers.append(
                "Required quantity is not confirmed."
            )

        if not requirement.unit:
            blockers.append(
                "Quantity unit is not confirmed."
            )

        if (
            candidate.buyer_readiness
            in {
                BuyerReadiness.UNKNOWN,
                BuyerReadiness.EARLY_INTEREST,
            }
        ):
            blockers.append(
                "Buyer requirement is not commercially confirmed."
            )

        if (
            candidate.payment_readiness
            == PaymentReadiness.UNKNOWN
        ):
            blockers.append(
                "Buyer payment readiness is unknown."
            )

        if (
            requirement.required_by_date
            and _parse_date(
                requirement.required_by_date
            )
            and _parse_date(
                requirement.required_by_date
            )
            < date.today()
        ):
            blockers.append(
                "Required delivery date has already passed."
            )

        return blockers

    @staticmethod
    def _warnings(
        candidate: DemandCandidate,
    ) -> list[str]:
        warnings = []
        buyer = candidate.buyer
        requirement = candidate.requirement

        if not buyer.contact_name:
            warnings.append(
                "Buyer contact name is not recorded."
            )
        if not buyer.contact_role:
            warnings.append(
                "Decision-maker role is not recorded."
            )
        if not buyer.email and not buyer.phone:
            warnings.append(
                "No direct buyer contact method is recorded."
            )
        if not buyer.registration_number:
            warnings.append(
                "Company registration number is not recorded."
            )
        if requirement.target_price is None:
            warnings.append(
                "Buyer target price or budget is not recorded."
            )
        if not requirement.preferred_incoterm:
            warnings.append(
                "Preferred Incoterm is not recorded."
            )
        if not candidate.evidence:
            warnings.append(
                "No demand evidence is attached."
            )
        if not requirement.required_by_date:
            warnings.append(
                "Required delivery date is not recorded."
            )

        return warnings

    @staticmethod
    def _strengths(
        candidate: DemandCandidate,
        *,
        identity_score: int,
        requirement_score: int,
        evidence_score: int,
    ) -> list[str]:
        strengths = []

        if identity_score >= 75:
            strengths.append(
                "Buyer identity is well documented."
            )
        if requirement_score >= 75:
            strengths.append(
                "Product requirement is sufficiently detailed."
            )
        if evidence_score >= 70:
            strengths.append(
                "Demand is supported by credible evidence."
            )
        if (
            candidate.buyer_readiness
            in {
                BuyerReadiness.READY_TO_BUY,
                BuyerReadiness.PURCHASE_APPROVED,
            }
        ):
            strengths.append(
                "Buyer has strong commercial readiness."
            )
        if (
            candidate.payment_readiness
            in {
                PaymentReadiness.FULL_PAYMENT_READY,
                PaymentReadiness.FUNDS_CLEARED,
            }
        ):
            strengths.append(
                "Buyer has strong payment readiness."
            )

        return strengths

    @staticmethod
    def _confidence_score(
        candidate: DemandCandidate,
        *,
        identity_score: int,
        requirement_score: int,
        evidence_score: int,
    ) -> int:
        source_confidence = {
            DemandSourceType.DIRECT_BUYER_REQUEST: 90,
            DemandSourceType.SIGNED_REQUIREMENT
            if hasattr(DemandSourceType, "SIGNED_REQUIREMENT")
            else DemandSourceType.DIRECT_BUYER_REQUEST: 90,
            DemandSourceType.GOVERNMENT_TENDER: 85,
            DemandSourceType.PUBLIC_TENDER: 80,
            DemandSourceType.EMAIL: 75,
            DemandSourceType.WEBSITE_ENQUIRY: 70,
            DemandSourceType.PARTNER_REFERRAL: 65,
            DemandSourceType.SALES_CONVERSATION: 65,
            DemandSourceType.PHONE: 55,
            DemandSourceType.WHATSAPP: 55,
            DemandSourceType.MARKETPLACE: 50,
            DemandSourceType.WEB_DISCOVERY: 40,
            DemandSourceType.MARKET_RESEARCH: 35,
            DemandSourceType.IMPORT_DATA: 45,
            DemandSourceType.DISTRIBUTOR_SIGNAL: 40,
            DemandSourceType.RETAILER_SIGNAL: 40,
            DemandSourceType.WHOLESALER_SIGNAL: 40,
            DemandSourceType.MANUAL_ENTRY: 50,
            DemandSourceType.OTHER: 35,
        }.get(candidate.source_type, 40)

        return max(
            0,
            min(
                100,
                round(
                    source_confidence * 0.25
                    + identity_score * 0.25
                    + requirement_score * 0.25
                    + evidence_score * 0.25
                ),
            ),
        )

    @staticmethod
    def _verification_status(
        candidate: DemandCandidate,
        *,
        identity_score: int,
        evidence_score: int,
    ) -> VerificationStatus:
        if (
            candidate.buyer.verification_status
            == VerificationStatus.FAILED
        ):
            return VerificationStatus.FAILED

        if (
            candidate.buyer.verification_status
            == VerificationStatus.VERIFIED
            and identity_score >= 75
            and evidence_score >= 65
        ):
            return VerificationStatus.VERIFIED

        if (
            identity_score >= 55
            and evidence_score >= 45
        ):
            return VerificationStatus.PARTIALLY_VERIFIED

        return VerificationStatus.UNVERIFIED

    @staticmethod
    def _recommended_status(
        candidate: DemandCandidate,
        *,
        verification_status: VerificationStatus,
        matching_allowed: bool,
        supplier_outreach_allowed: bool,
        binding_action_allowed: bool,
        blockers: list[str],
    ) -> DemandStatus:
        if (
            verification_status
            == VerificationStatus.FAILED
        ):
            return DemandStatus.REJECTED

        if binding_action_allowed:
            return DemandStatus.ACCEPTED

        if supplier_outreach_allowed:
            return DemandStatus.READY_FOR_MATCHING

        if matching_allowed:
            return DemandStatus.QUALIFIED

        if blockers:
            return DemandStatus.NEEDS_INFORMATION

        return DemandStatus.UNDER_REVIEW

    @staticmethod
    def _priority(
        *,
        weighted_score: int,
        urgency_score: int,
        buyer_readiness_score: int,
        payment_readiness_score: int,
    ) -> DemandPriority:
        combined = round(
            weighted_score * 0.45
            + urgency_score * 0.20
            + buyer_readiness_score * 0.20
            + payment_readiness_score * 0.15
        )

        if combined >= 85:
            return DemandPriority.CRITICAL
        if combined >= 70:
            return DemandPriority.HIGH
        if combined >= 50:
            return DemandPriority.MEDIUM
        return DemandPriority.LOW

    @staticmethod
    def _next_actions(
        candidate: DemandCandidate,
        *,
        blockers: list[str],
        verification_status: VerificationStatus,
        matching_allowed: bool,
        supplier_outreach_allowed: bool,
    ) -> list[str]:
        actions = []

        if (
            verification_status
            != VerificationStatus.VERIFIED
        ):
            actions.append(
                "Verify buyer company identity, registration and authorised contact."
            )

        if not candidate.requirement.specification:
            actions.append(
                "Obtain the final product specification from the buyer."
            )

        if (
            candidate.requirement.quantity is None
            or candidate.requirement.quantity <= 0
        ):
            actions.append(
                "Confirm quantity, unit and repeat purchase frequency."
            )

        if (
            candidate.requirement.target_price is None
        ):
            actions.append(
                "Confirm buyer budget, target price or acceptable price range."
            )

        if (
            candidate.payment_readiness
            in {
                PaymentReadiness.UNKNOWN,
                PaymentReadiness.NOT_DISCLOSED,
                PaymentReadiness.SUBJECT_TO_APPROVAL,
                PaymentReadiness.CREDIT_REVIEW_REQUIRED,
            }
        ):
            actions.append(
                "Complete payment-readiness or credit review before supplier commitment."
            )

        if matching_allowed and not supplier_outreach_allowed:
            actions.append(
                "Complete remaining demand evidence before supplier outreach."
            )

        if supplier_outreach_allowed:
            actions.append(
                "Send the verified demand to the demand–supply matching engine."
            )

        if not actions and blockers:
            actions.append(
                "Resolve all demand blockers before progressing."
            )

        return actions

    @staticmethod
    def _critical_matching_blockers(
        blockers: list[str],
    ) -> bool:
        critical_phrases = {
            "Buyer verification failed.",
            "Buyer company identity is missing.",
            "Required product is missing.",
            "Product specification is not confirmed.",
            "Required quantity is not confirmed.",
            "Quantity unit is not confirmed.",
            "Buyer requirement is not commercially confirmed.",
        }
        return any(
            item in critical_phrases
            for item in blockers
        )

    @staticmethod
    def _explanation(
        candidate: DemandCandidate,
        *,
        weighted_score: int,
        confidence_score: int,
        verification_status: VerificationStatus,
        matching_allowed: bool,
        supplier_outreach_allowed: bool,
        binding_action_allowed: bool,
        blockers: list[str],
    ) -> str:
        return (
            f"Demand '{candidate.title}' scored {weighted_score}/100 with "
            f"{confidence_score}/100 confidence. Buyer and demand verification "
            f"status is {verification_status.value}. Supplier matching is "
            f"{'allowed' if matching_allowed else 'not allowed'}, supplier "
            f"outreach is {'allowed' if supplier_outreach_allowed else 'not allowed'}, "
            f"and binding action is {'allowed' if binding_action_allowed else 'not allowed'}. "
            f"{len(blockers)} blocker(s) remain."
        )

    def _upsert_record(
        self,
        candidate: DemandCandidate,
        assessment: DemandAssessment,
        *,
        fingerprint: str,
    ) -> None:
        now = _now()
        buyer = candidate.buyer
        requirement = candidate.requirement

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO global_demand_records (
                    demand_id,
                    fingerprint,
                    title,
                    buyer_id,
                    buyer_company,
                    buyer_type,
                    buyer_country,
                    buyer_city,
                    contact_name,
                    contact_role,
                    contact_email,
                    contact_phone,
                    buyer_website,
                    registration_number,
                    tax_number,
                    buyer_verification_status,
                    buyer_credit_status,
                    product_name,
                    product_category,
                    specification,
                    quality_grade,
                    brand_requirement,
                    packaging,
                    private_label_required,
                    quantity,
                    unit,
                    repeat_frequency,
                    target_price,
                    currency,
                    preferred_incoterm,
                    destination_country,
                    destination_city,
                    destination_port,
                    required_by_date,
                    certificates_required_json,
                    compliance_requirements_json,
                    sample_required,
                    source_type,
                    source_reference,
                    source_url,
                    buyer_readiness,
                    payment_readiness,
                    status,
                    overall_score,
                    confidence_score,
                    priority,
                    matching_allowed,
                    supplier_outreach_allowed,
                    binding_action_allowed,
                    blockers_json,
                    warnings_json,
                    strengths_json,
                    next_actions_json,
                    explanation,
                    notes,
                    assigned_owner,
                    created_by,
                    metadata_json,
                    created_at,
                    updated_at,
                    last_assessed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(demand_id)
                DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    title = excluded.title,
                    buyer_id = excluded.buyer_id,
                    buyer_company = excluded.buyer_company,
                    buyer_type = excluded.buyer_type,
                    buyer_country = excluded.buyer_country,
                    buyer_city = excluded.buyer_city,
                    contact_name = excluded.contact_name,
                    contact_role = excluded.contact_role,
                    contact_email = excluded.contact_email,
                    contact_phone = excluded.contact_phone,
                    buyer_website = excluded.buyer_website,
                    registration_number = excluded.registration_number,
                    tax_number = excluded.tax_number,
                    buyer_verification_status = excluded.buyer_verification_status,
                    buyer_credit_status = excluded.buyer_credit_status,
                    product_name = excluded.product_name,
                    product_category = excluded.product_category,
                    specification = excluded.specification,
                    quality_grade = excluded.quality_grade,
                    brand_requirement = excluded.brand_requirement,
                    packaging = excluded.packaging,
                    private_label_required = excluded.private_label_required,
                    quantity = excluded.quantity,
                    unit = excluded.unit,
                    repeat_frequency = excluded.repeat_frequency,
                    target_price = excluded.target_price,
                    currency = excluded.currency,
                    preferred_incoterm = excluded.preferred_incoterm,
                    destination_country = excluded.destination_country,
                    destination_city = excluded.destination_city,
                    destination_port = excluded.destination_port,
                    required_by_date = excluded.required_by_date,
                    certificates_required_json = excluded.certificates_required_json,
                    compliance_requirements_json = excluded.compliance_requirements_json,
                    sample_required = excluded.sample_required,
                    source_type = excluded.source_type,
                    source_reference = excluded.source_reference,
                    source_url = excluded.source_url,
                    buyer_readiness = excluded.buyer_readiness,
                    payment_readiness = excluded.payment_readiness,
                    status = excluded.status,
                    overall_score = excluded.overall_score,
                    confidence_score = excluded.confidence_score,
                    priority = excluded.priority,
                    matching_allowed = excluded.matching_allowed,
                    supplier_outreach_allowed = excluded.supplier_outreach_allowed,
                    binding_action_allowed = excluded.binding_action_allowed,
                    blockers_json = excluded.blockers_json,
                    warnings_json = excluded.warnings_json,
                    strengths_json = excluded.strengths_json,
                    next_actions_json = excluded.next_actions_json,
                    explanation = excluded.explanation,
                    notes = excluded.notes,
                    assigned_owner = excluded.assigned_owner,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    last_assessed_at = excluded.last_assessed_at
                """,
                (
                    candidate.demand_id,
                    fingerprint,
                    candidate.title,
                    buyer.buyer_id,
                    buyer.company_name,
                    buyer.buyer_type,
                    buyer.country,
                    buyer.city,
                    buyer.contact_name,
                    buyer.contact_role,
                    buyer.email,
                    buyer.phone,
                    buyer.website,
                    buyer.registration_number,
                    buyer.tax_number,
                    assessment.verification_status.value,
                    buyer.credit_status,
                    requirement.product_name,
                    requirement.category,
                    requirement.specification,
                    requirement.quality_grade,
                    requirement.brand_requirement,
                    requirement.packaging,
                    1 if requirement.private_label_required else 0,
                    requirement.quantity,
                    requirement.unit,
                    requirement.repeat_frequency,
                    requirement.target_price,
                    requirement.currency,
                    requirement.preferred_incoterm,
                    requirement.destination_country,
                    requirement.destination_city,
                    requirement.destination_port,
                    requirement.required_by_date,
                    json.dumps(
                        list(requirement.certificates_required),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        list(requirement.compliance_requirements),
                        ensure_ascii=False,
                    ),
                    1 if requirement.sample_required else 0,
                    candidate.source_type.value,
                    candidate.source_reference,
                    candidate.source_url,
                    candidate.buyer_readiness.value,
                    candidate.payment_readiness.value,
                    assessment.recommended_status.value,
                    assessment.overall_score,
                    assessment.confidence_score,
                    assessment.priority.value,
                    1 if assessment.matching_allowed else 0,
                    1 if assessment.supplier_outreach_allowed else 0,
                    1 if assessment.binding_action_allowed else 0,
                    json.dumps(
                        list(assessment.blockers),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        list(assessment.warnings),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        list(assessment.strengths),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        list(assessment.next_actions),
                        ensure_ascii=False,
                    ),
                    assessment.explanation,
                    candidate.notes,
                    candidate.assigned_owner,
                    candidate.created_by,
                    json.dumps(
                        candidate.metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    candidate.created_at,
                    now,
                    assessment.assessed_at,
                ),
            )
            connection.commit()

    def _persist_evidence(
        self,
        demand_id: str,
        evidence_items: Iterable[DemandEvidence],
    ) -> int:
        created = 0

        with get_connection() as connection:
            for item in evidence_items:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO global_demand_evidence (
                        evidence_id,
                        demand_id,
                        evidence_type,
                        title,
                        summary,
                        source_reference,
                        source_url,
                        document_reference,
                        verified,
                        confidence_score,
                        metadata_json,
                        observed_at,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.evidence_id,
                        demand_id,
                        item.evidence_type.value,
                        item.title,
                        item.summary,
                        item.source_reference,
                        item.source_url,
                        item.document_reference,
                        1 if item.verified else 0,
                        item.confidence_score,
                        json.dumps(
                            item.metadata,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        item.observed_at,
                        _now(),
                    ),
                )
                created += cursor.rowcount

            connection.commit()

        return created

    def _find_by_fingerprint(
        self,
        fingerprint: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM global_demand_records
                WHERE fingerprint = ?
                LIMIT 1
                """,
                (fingerprint,),
            ).fetchone()

        return (
            self._decode_record(row)
            if row
            else None
        )

    def _record_status_change(
        self,
        demand_id: str,
        *,
        previous_status: str | None,
        new_status: str,
        reason: str,
        changed_by: str,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO global_demand_status_history (
                    demand_id,
                    previous_status,
                    new_status,
                    reason,
                    changed_by,
                    changed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    demand_id,
                    previous_status,
                    new_status,
                    reason,
                    changed_by,
                    _now(),
                ),
            )
            connection.commit()

    def _audit(
        self,
        *,
        demand_id: str | None,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> str:
        audit_id = f"AUD-{uuid4().hex[:16].upper()}"

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO global_demand_audit (
                    audit_id,
                    demand_id,
                    action,
                    actor,
                    details_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    demand_id,
                    action,
                    actor,
                    json.dumps(
                        details,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    _now(),
                ),
            )
            connection.commit()

        return audit_id

    @staticmethod
    def _fingerprint(
        candidate: DemandCandidate,
    ) -> str:
        requirement = candidate.requirement
        buyer = candidate.buyer

        raw = "|".join(
            [
                buyer.company_name.lower(),
                buyer.country.lower(),
                requirement.product_name.lower(),
                requirement.destination_country.lower(),
                str(requirement.quantity or ""),
                str(requirement.unit or "").lower(),
                str(requirement.required_by_date or ""),
                candidate.source_reference.lower(),
            ]
        )

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _decode_record(
        row: Any,
    ) -> dict[str, Any]:
        record = dict(row)

        for key in (
            "certificates_required_json",
            "compliance_requirements_json",
            "blockers_json",
            "warnings_json",
            "strengths_json",
            "next_actions_json",
            "metadata_json",
        ):
            decoded_key = key.removesuffix("_json")
            record[decoded_key] = _decode_json(
                record.get(key),
                [] if key != "metadata_json" else {},
            )

        for key in (
            "private_label_required",
            "sample_required",
            "matching_allowed",
            "supplier_outreach_allowed",
            "binding_action_allowed",
        ):
            record[key] = bool(record.get(key))

        return record

    @staticmethod
    def _decode_evidence_row(
        row: Any,
    ) -> dict[str, Any]:
        record = dict(row)
        record["verified"] = bool(
            record.get("verified")
        )
        record["metadata"] = _decode_json(
            record.get("metadata_json"),
            {},
        )
        return record

    @staticmethod
    def _record_to_candidate(
        record: dict[str, Any],
    ) -> DemandCandidate:
        evidence = tuple(
            DemandEvidence(
                evidence_id=item["evidence_id"],
                evidence_type=EvidenceType(
                    item["evidence_type"]
                ),
                title=item["title"],
                summary=item["summary"],
                source_reference=item[
                    "source_reference"
                ],
                source_url=item.get("source_url"),
                document_reference=item.get(
                    "document_reference"
                ),
                verified=bool(item.get("verified")),
                confidence_score=int(
                    item.get("confidence_score", 50)
                ),
                observed_at=item["observed_at"],
                metadata=item.get("metadata", {}),
            )
            for item in record.get("evidence", [])
        )

        buyer = BuyerIdentity(
            buyer_id=record.get("buyer_id"),
            company_name=record["buyer_company"],
            buyer_type=record["buyer_type"],
            country=record["buyer_country"],
            city=record.get("buyer_city"),
            contact_name=record.get("contact_name"),
            contact_role=record.get("contact_role"),
            email=record.get("contact_email"),
            phone=record.get("contact_phone"),
            website=record.get("buyer_website"),
            registration_number=record.get(
                "registration_number"
            ),
            tax_number=record.get("tax_number"),
            verification_status=VerificationStatus(
                record["buyer_verification_status"]
            ),
            credit_status=record.get(
                "buyer_credit_status"
            ),
        )

        requirement = ProductRequirement(
            product_name=record["product_name"],
            category=record.get("product_category"),
            specification=record.get("specification"),
            quality_grade=record.get("quality_grade"),
            brand_requirement=record.get(
                "brand_requirement"
            ),
            packaging=record.get("packaging"),
            private_label_required=bool(
                record.get("private_label_required")
            ),
            quantity=record.get("quantity"),
            unit=record.get("unit"),
            repeat_frequency=record.get(
                "repeat_frequency"
            ),
            target_price=record.get("target_price"),
            currency=record["currency"],
            preferred_incoterm=record.get(
                "preferred_incoterm"
            ),
            destination_country=record[
                "destination_country"
            ],
            destination_city=record.get(
                "destination_city"
            ),
            destination_port=record.get(
                "destination_port"
            ),
            required_by_date=record.get(
                "required_by_date"
            ),
            certificates_required=tuple(
                record.get(
                    "certificates_required",
                    [],
                )
            ),
            compliance_requirements=tuple(
                record.get(
                    "compliance_requirements",
                    [],
                )
            ),
            sample_required=bool(
                record.get("sample_required")
            ),
        )

        return DemandCandidate(
            demand_id=record["demand_id"],
            title=record["title"],
            buyer=buyer,
            requirement=requirement,
            source_type=DemandSourceType(
                record["source_type"]
            ),
            source_reference=record[
                "source_reference"
            ],
            source_url=record.get("source_url"),
            buyer_readiness=BuyerReadiness(
                record["buyer_readiness"]
            ),
            payment_readiness=PaymentReadiness(
                record["payment_readiness"]
            ),
            status=DemandStatus(record["status"]),
            evidence=evidence,
            notes=record.get("notes", ""),
            assigned_owner=record.get(
                "assigned_owner"
            ),
            created_by=record.get(
                "created_by",
                "System",
            ),
            created_at=record["created_at"],
            metadata=record.get("metadata", {}),
        )

    @staticmethod
    def _new_demand_id() -> str:
        return f"DEM-{uuid4().hex[:16].upper()}"


def _clean_required(
    value: Any,
    field_name: str,
) -> str:
    cleaned = _clean_optional(value)

    if not cleaned:
        raise ValueError(
            f"{field_name} is required."
        )

    return cleaned


def _clean_optional(
    value: Any,
) -> str | None:
    if value is None:
        return None

    cleaned = re.sub(
        r"\s+",
        " ",
        str(value).strip(),
    )

    return cleaned or None


def _normalize_email(
    value: Any,
) -> str | None:
    cleaned = _clean_optional(value)

    if not cleaned:
        return None

    lowered = cleaned.lower()

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        lowered,
    ):
        return cleaned

    return lowered


def _normalize_url(
    value: Any,
) -> str | None:
    cleaned = _clean_optional(value)

    if not cleaned:
        return None

    if cleaned.startswith(
        ("http://", "https://")
    ):
        return cleaned

    return f"https://{cleaned}"


def _normalize_date(
    value: Any,
) -> str | None:
    cleaned = _clean_optional(value)

    if not cleaned:
        return None

    try:
        return datetime.fromisoformat(
            cleaned[:10]
        ).date().isoformat()
    except ValueError:
        return cleaned


def _parse_date(
    value: Any,
) -> date | None:
    cleaned = _clean_optional(value)

    if not cleaned:
        return None

    try:
        return datetime.strptime(
            cleaned[:10],
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def _positive_number_or_none(
    value: Any,
) -> float | None:
    if value in (None, ""):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if number > 0 else None


def _unique_clean_strings(
    values: Iterable[Any],
) -> list[str]:
    unique: dict[str, str] = {}

    for value in values:
        cleaned = _clean_optional(value)

        if cleaned:
            unique.setdefault(
                cleaned.lower(),
                cleaned,
            )

    return list(unique.values())


def _decode_json(
    value: str | None,
    default: Any,
) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _now() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


_global_demand_engine = GlobalDemandIntelligenceEngine()


def get_global_demand_intelligence_engine() -> GlobalDemandIntelligenceEngine:
    """Return the GPNI demand intelligence singleton."""

    return _global_demand_engine


def ingest_global_demand(
    candidate: DemandCandidate,
    *,
    actor: str = "Global Demand Intelligence Engine",
) -> DemandIntelligenceReport:
    """Normalize, assess and persist a global demand candidate."""

    return _global_demand_engine.ingest(
        candidate,
        actor=actor,
    )


def assess_global_demand(
    candidate: DemandCandidate,
) -> DemandAssessment:
    """Assess a demand candidate without persisting it."""

    normalized = _global_demand_engine.normalize_candidate(
        candidate
    )
    return _global_demand_engine.assess(
        normalized
    )


def list_match_ready_demands(
    *,
    product_name: str | None = None,
    destination_country: str | None = None,
    minimum_score: int = 65,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return demands eligible for supply matching."""

    return _global_demand_engine.list_demands(
        product_name=product_name,
        destination_country=destination_country,
        matching_allowed=True,
        minimum_score=minimum_score,
        limit=limit,
    )