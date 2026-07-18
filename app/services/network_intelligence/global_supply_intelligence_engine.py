"""Global Supply Intelligence Engine for GPNI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from database.connection import get_connection


class SupplyStatus(str, Enum):
    NEW = "New"
    UNDER_REVIEW = "Under Review"
    NEEDS_INFORMATION = "Needs Information"
    QUALIFIED = "Qualified"
    VERIFIED = "Verified"
    READY_FOR_MATCHING = "Ready for Matching"
    SUSPENDED = "Suspended"
    REJECTED = "Rejected"


class SupplyVerificationStatus(str, Enum):
    UNVERIFIED = "Unverified"
    PARTIALLY_VERIFIED = "Partially Verified"
    VERIFIED = "Verified"
    FAILED = "Failed"


class ExportReadiness(str, Enum):
    UNKNOWN = "Unknown"
    DOMESTIC_ONLY = "Domestic Only"
    DOCUMENTS_PENDING = "Documents Pending"
    EXPORT_CAPABLE = "Export Capable"
    EXPORT_READY = "Export Ready"


@dataclass(frozen=True)
class SupplyEvidence:
    evidence_id: str
    title: str
    summary: str
    source_reference: str
    verified: bool = False
    confidence_score: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupplierProfile:
    supplier_id: str
    company_name: str
    supplier_type: str
    country: str
    city: str | None = None
    website: str | None = None
    registration_number: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    verification_status: SupplyVerificationStatus = SupplyVerificationStatus.UNVERIFIED
    export_readiness: ExportReadiness = ExportReadiness.UNKNOWN
    years_in_business: int | None = None
    factory_audited: bool = False
    sanctions_cleared: bool = False


@dataclass(frozen=True)
class SupplyCapability:
    product_name: str
    category: str | None = None
    specification: str | None = None
    capacity: float | None = None
    capacity_unit: str | None = None
    minimum_order_quantity: float | None = None
    lead_time_days: int | None = None
    unit_price: float | None = None
    currency: str = "USD"
    incoterms: tuple[str, ...] = ()
    packaging_options: tuple[str, ...] = ()
    certificates: tuple[str, ...] = ()
    export_markets: tuple[str, ...] = ()
    sample_available: bool = False


@dataclass(frozen=True)
class SupplyCandidate:
    supply_id: str
    supplier: SupplierProfile
    capability: SupplyCapability
    source_reference: str
    evidence: tuple[SupplyEvidence, ...] = ()
    notes: str = ""
    created_by: str = "System"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupplyAssessment:
    supply_id: str
    overall_score: int
    confidence_score: int
    verification_score: int
    capability_score: int
    export_score: int
    documentation_score: int
    commercial_score: int
    matching_allowed: bool
    quotation_request_allowed: bool
    binding_action_allowed: bool
    recommended_status: SupplyStatus
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_actions: tuple[str, ...]
    explanation: str


def create_global_supply_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_supply_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supply_id TEXT NOT NULL UNIQUE,
                fingerprint TEXT NOT NULL UNIQUE,
                supplier_id TEXT NOT NULL,
                company_name TEXT NOT NULL,
                supplier_type TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT,
                website TEXT,
                registration_number TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                verification_status TEXT NOT NULL,
                export_readiness TEXT NOT NULL,
                years_in_business INTEGER,
                factory_audited INTEGER NOT NULL DEFAULT 0,
                sanctions_cleared INTEGER NOT NULL DEFAULT 0,
                product_name TEXT NOT NULL,
                category TEXT,
                specification TEXT,
                capacity REAL,
                capacity_unit TEXT,
                minimum_order_quantity REAL,
                lead_time_days INTEGER,
                unit_price REAL,
                currency TEXT NOT NULL,
                incoterms_json TEXT NOT NULL DEFAULT '[]',
                packaging_options_json TEXT NOT NULL DEFAULT '[]',
                certificates_json TEXT NOT NULL DEFAULT '[]',
                export_markets_json TEXT NOT NULL DEFAULT '[]',
                sample_available INTEGER NOT NULL DEFAULT 0,
                source_reference TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                confidence_score INTEGER NOT NULL,
                matching_allowed INTEGER NOT NULL DEFAULT 0,
                quotation_request_allowed INTEGER NOT NULL DEFAULT 0,
                binding_action_allowed INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                blockers_json TEXT NOT NULL DEFAULT '[]',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                next_actions_json TEXT NOT NULL DEFAULT '[]',
                explanation TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_supply_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL UNIQUE,
                supply_id TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                confidence_score INTEGER NOT NULL DEFAULT 50,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (supply_id)
                    REFERENCES global_supply_records(supply_id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_supply_product
            ON global_supply_records(product_name, country, status)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_supply_matching
            ON global_supply_records(matching_allowed, overall_score DESC)
            """
        )
        connection.commit()


class GlobalSupplyIntelligenceEngine:
    def __init__(self) -> None:
        create_global_supply_tables()

    def assess(self, candidate: SupplyCandidate) -> SupplyAssessment:
        supplier = candidate.supplier
        capability = candidate.capability

        verification_score = 20
        if supplier.registration_number:
            verification_score += 20
        if supplier.website:
            verification_score += 10
        if supplier.contact_name and supplier.email:
            verification_score += 10
        if supplier.factory_audited:
            verification_score += 20
        if supplier.sanctions_cleared:
            verification_score += 20
        if supplier.verification_status == SupplyVerificationStatus.VERIFIED:
            verification_score += 20
        elif supplier.verification_status == SupplyVerificationStatus.FAILED:
            verification_score = 0
        verification_score = min(100, verification_score)

        capability_score = 20
        if capability.specification:
            capability_score += 20
        if capability.capacity and capability.capacity > 0:
            capability_score += 15
        if capability.minimum_order_quantity and capability.minimum_order_quantity > 0:
            capability_score += 10
        if capability.lead_time_days and capability.lead_time_days > 0:
            capability_score += 10
        if capability.packaging_options:
            capability_score += 10
        if capability.sample_available:
            capability_score += 10
        capability_score = min(100, capability_score)

        export_score = {
            ExportReadiness.UNKNOWN: 10,
            ExportReadiness.DOMESTIC_ONLY: 15,
            ExportReadiness.DOCUMENTS_PENDING: 45,
            ExportReadiness.EXPORT_CAPABLE: 75,
            ExportReadiness.EXPORT_READY: 100,
        }[supplier.export_readiness]

        documentation_score = min(
            100,
            len(capability.certificates) * 15
            + len(candidate.evidence) * 8
            + sum(10 for item in candidate.evidence if item.verified),
        )

        commercial_score = 20
        if capability.unit_price and capability.unit_price > 0:
            commercial_score += 25
        if capability.currency:
            commercial_score += 10
        if capability.incoterms:
            commercial_score += 20
        if capability.lead_time_days:
            commercial_score += 10
        if capability.minimum_order_quantity:
            commercial_score += 10
        commercial_score = min(100, commercial_score)

        confidence_score = round(
            verification_score * 0.35
            + documentation_score * 0.30
            + capability_score * 0.20
            + export_score * 0.15
        )

        overall_score = round(
            verification_score * 0.25
            + capability_score * 0.25
            + export_score * 0.20
            + documentation_score * 0.15
            + commercial_score * 0.15
        )

        blockers: list[str] = []
        warnings: list[str] = []

        if supplier.verification_status == SupplyVerificationStatus.FAILED:
            blockers.append("Supplier verification failed.")
        if not supplier.registration_number:
            blockers.append("Supplier registration is not confirmed.")
        if not capability.specification:
            blockers.append("Product specification is not confirmed.")
        if not capability.capacity:
            blockers.append("Production or supply capacity is not confirmed.")
        if supplier.export_readiness in {
            ExportReadiness.UNKNOWN,
            ExportReadiness.DOMESTIC_ONLY,
        }:
            blockers.append("Supplier is not confirmed as export-ready.")
        if not supplier.sanctions_cleared:
            blockers.append("Sanctions and restricted-party screening is incomplete.")
        if not capability.certificates:
            warnings.append("No product or factory certificates are recorded.")
        if not capability.unit_price:
            warnings.append("Indicative supplier pricing is not recorded.")
        if not capability.incoterms:
            warnings.append("Supported Incoterms are not recorded.")

        matching_allowed = (
            overall_score >= 65
            and confidence_score >= 60
            and not any(
                blocker in {
                    "Supplier verification failed.",
                    "Product specification is not confirmed.",
                    "Production or supply capacity is not confirmed.",
                    "Supplier is not confirmed as export-ready.",
                }
                for blocker in blockers
            )
        )
        quotation_request_allowed = (
            matching_allowed
            and supplier.verification_status
            in {
                SupplyVerificationStatus.PARTIALLY_VERIFIED,
                SupplyVerificationStatus.VERIFIED,
            }
        )
        binding_action_allowed = (
            quotation_request_allowed
            and supplier.verification_status == SupplyVerificationStatus.VERIFIED
            and supplier.export_readiness == ExportReadiness.EXPORT_READY
            and supplier.sanctions_cleared
            and not blockers
        )

        if supplier.verification_status == SupplyVerificationStatus.FAILED:
            status = SupplyStatus.REJECTED
        elif binding_action_allowed:
            status = SupplyStatus.VERIFIED
        elif quotation_request_allowed:
            status = SupplyStatus.READY_FOR_MATCHING
        elif matching_allowed:
            status = SupplyStatus.QUALIFIED
        elif blockers:
            status = SupplyStatus.NEEDS_INFORMATION
        else:
            status = SupplyStatus.UNDER_REVIEW

        actions = []
        if not supplier.registration_number:
            actions.append("Verify legal registration and beneficial ownership.")
        if not supplier.sanctions_cleared:
            actions.append("Complete sanctions and restricted-party screening.")
        if not capability.capacity:
            actions.append("Confirm monthly production or supply capacity.")
        if not capability.certificates:
            actions.append("Collect and verify applicable certificates.")
        if not capability.unit_price:
            actions.append("Request an indicative export quotation.")
        if matching_allowed:
            actions.append("Send eligible supply to the matching engine.")

        explanation = (
            f"Supply scored {overall_score}/100 with {confidence_score}/100 confidence. "
            f"Matching is {'allowed' if matching_allowed else 'not allowed'}, "
            f"quotation requests are {'allowed' if quotation_request_allowed else 'not allowed'}, "
            f"and binding action is {'allowed' if binding_action_allowed else 'not allowed'}."
        )

        return SupplyAssessment(
            supply_id=candidate.supply_id,
            overall_score=overall_score,
            confidence_score=confidence_score,
            verification_score=verification_score,
            capability_score=capability_score,
            export_score=export_score,
            documentation_score=documentation_score,
            commercial_score=commercial_score,
            matching_allowed=matching_allowed,
            quotation_request_allowed=quotation_request_allowed,
            binding_action_allowed=binding_action_allowed,
            recommended_status=status,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            next_actions=tuple(actions),
            explanation=explanation,
        )

    def ingest(
        self,
        candidate: SupplyCandidate,
        *,
        actor: str = "Global Supply Intelligence Engine",
    ) -> SupplyAssessment:
        assessment = self.assess(candidate)
        fingerprint = self._fingerprint(candidate)
        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO global_supply_records (
                    supply_id, fingerprint, supplier_id, company_name,
                    supplier_type, country, city, website, registration_number,
                    contact_name, email, phone, verification_status,
                    export_readiness, years_in_business, factory_audited,
                    sanctions_cleared, product_name, category, specification,
                    capacity, capacity_unit, minimum_order_quantity,
                    lead_time_days, unit_price, currency, incoterms_json,
                    packaging_options_json, certificates_json,
                    export_markets_json, sample_available, source_reference,
                    overall_score, confidence_score, matching_allowed,
                    quotation_request_allowed, binding_action_allowed, status,
                    blockers_json, warnings_json, next_actions_json,
                    explanation, notes, created_by, metadata_json,
                    created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(supply_id)
                DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    verification_status = excluded.verification_status,
                    export_readiness = excluded.export_readiness,
                    overall_score = excluded.overall_score,
                    confidence_score = excluded.confidence_score,
                    matching_allowed = excluded.matching_allowed,
                    quotation_request_allowed = excluded.quotation_request_allowed,
                    binding_action_allowed = excluded.binding_action_allowed,
                    status = excluded.status,
                    blockers_json = excluded.blockers_json,
                    warnings_json = excluded.warnings_json,
                    next_actions_json = excluded.next_actions_json,
                    explanation = excluded.explanation,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    candidate.supply_id,
                    fingerprint,
                    candidate.supplier.supplier_id,
                    candidate.supplier.company_name,
                    candidate.supplier.supplier_type,
                    candidate.supplier.country,
                    candidate.supplier.city,
                    candidate.supplier.website,
                    candidate.supplier.registration_number,
                    candidate.supplier.contact_name,
                    candidate.supplier.email,
                    candidate.supplier.phone,
                    candidate.supplier.verification_status.value,
                    candidate.supplier.export_readiness.value,
                    candidate.supplier.years_in_business,
                    int(candidate.supplier.factory_audited),
                    int(candidate.supplier.sanctions_cleared),
                    candidate.capability.product_name,
                    candidate.capability.category,
                    candidate.capability.specification,
                    candidate.capability.capacity,
                    candidate.capability.capacity_unit,
                    candidate.capability.minimum_order_quantity,
                    candidate.capability.lead_time_days,
                    candidate.capability.unit_price,
                    candidate.capability.currency,
                    json.dumps(candidate.capability.incoterms),
                    json.dumps(candidate.capability.packaging_options),
                    json.dumps(candidate.capability.certificates),
                    json.dumps(candidate.capability.export_markets),
                    int(candidate.capability.sample_available),
                    candidate.source_reference,
                    assessment.overall_score,
                    assessment.confidence_score,
                    int(assessment.matching_allowed),
                    int(assessment.quotation_request_allowed),
                    int(assessment.binding_action_allowed),
                    assessment.recommended_status.value,
                    json.dumps(assessment.blockers),
                    json.dumps(assessment.warnings),
                    json.dumps(assessment.next_actions),
                    assessment.explanation,
                    candidate.notes,
                    candidate.created_by,
                    json.dumps(candidate.metadata),
                    now,
                    now,
                ),
            )

            for evidence in candidate.evidence:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO global_supply_evidence (
                        evidence_id, supply_id, title, summary,
                        source_reference, verified, confidence_score,
                        metadata_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence.evidence_id,
                        candidate.supply_id,
                        evidence.title,
                        evidence.summary,
                        evidence.source_reference,
                        int(evidence.verified),
                        evidence.confidence_score,
                        json.dumps(evidence.metadata),
                        now,
                    ),
                )

            connection.commit()

        return assessment

    @staticmethod
    def _fingerprint(candidate: SupplyCandidate) -> str:
        raw = "|".join(
            [
                candidate.supplier.company_name.lower(),
                candidate.supplier.country.lower(),
                candidate.capability.product_name.lower(),
                candidate.source_reference.lower(),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


_engine = GlobalSupplyIntelligenceEngine()


def get_global_supply_intelligence_engine() -> GlobalSupplyIntelligenceEngine:
    return _engine