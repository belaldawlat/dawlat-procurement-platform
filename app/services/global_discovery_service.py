"""
Global Supplier Discovery Service.

This service provides the domain layer for global supplier, manufacturer,
exporter and trade-partner discovery.

Design goals:
- provider-neutral architecture;
- clear separation between live-search adapters and business logic;
- structured company profiles;
- verification and certificate tracking;
- reusable support for rice, cricket, automotive, medical and future categories;
- no unverified company is treated as approved automatically.

A live search provider will be connected through a separate adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.global_search_provider import (
    SearchResponse,
    get_global_search_gateway,
)


SUPPORTED_PARTNER_TYPES = (
    "Supplier",
    "Manufacturer",
    "Exporter",
    "Freight Forwarder",
    "Customs Broker",
    "Warehouse",
    "3PL Provider",
    "Shipping Line",
    "Inspection Company",
    "Certification Company",
)

DEFAULT_VERIFICATION_CHECKLIST = (
    "Company legal identity",
    "Official website",
    "Business registration",
    "Factory or operating address",
    "Contact person and business email",
    "Product catalogue",
    "MOQ",
    "Pricing and currency",
    "Incoterms",
    "Lead time",
    "Payment terms",
    "Packaging capability",
    "Private-label capability",
    "Export markets",
    "Production or service capacity",
    "Relevant certificates",
    "Certificate validity",
    "Sample availability",
    "References or export history",
)


@dataclass(frozen=True)
class DiscoveryRequest:
    partner_type: str
    product: str
    country: str = ""
    destination: str = ""
    requirements: str = ""
    required_certificates: tuple[str, ...] = ()
    preferred_incoterms: tuple[str, ...] = ()
    maximum_lead_time_days: int | None = None
    minimum_confidence_score: int = 60


@dataclass
class CompanyCandidate:
    company_name: str
    partner_type: str
    country: str

    city: str = ""
    website: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    whatsapp: str = ""

    products_services: str = ""
    product_match: str = ""
    factory_address: str = ""
    company_registration: str = ""

    moq: str = ""
    price_information: str = ""
    currency: str = ""
    incoterms: str = ""
    lead_time: str = ""
    payment_terms: str = ""
    packaging: str = ""
    private_label: str = ""
    production_capacity: str = ""
    export_markets: str = ""
    samples: str = ""

    certificates: list[str] = field(default_factory=list)
    certificate_evidence: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)

    confidence_score: int = 0
    verification_status: str = "Unverified"
    risk_flags: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    notes: str = ""

    discovered_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass
class DiscoveryResult:
    success: bool
    request: DiscoveryRequest
    candidates: list[CompanyCandidate] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    live_responses: list[SearchResponse] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_name: str = "Not Connected"
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class GlobalDiscoveryService:
    """
    Business service for global company discovery.

    Live web providers must return structured CompanyCandidate records.
    This service then validates, scores and ranks those candidates.
    """

    def prepare_search(self, request: DiscoveryRequest) -> DiscoveryResult:
        """
        Prepare and execute a live global discovery search.

        External results remain unverified until reviewed and saved.
        """

        self._validate_request(request)

        queries = self._build_search_queries(request)
        gateway = get_global_search_gateway()

        responses = gateway.search_many(
            queries,
            country=request.country,
            language="en",
            max_results_per_query=5,
        )

        warnings: list[str] = []

        if not responses:
            warnings.append("No live search responses were returned.")

        failed = [
            response
            for response in responses
            if not response.success
        ]

        if failed:
            warnings.extend(
                response.error_message
                or "A live search request failed."
                for response in failed
            )

        if any(response.success for response in responses):
            warnings.append(
                "Live web results are unverified. Review the official "
                "company website, registration, certificates and contacts "
                "before saving or approving any company."
            )

        return DiscoveryResult(
            success=any(response.success for response in responses),
            request=request,
            search_queries=queries,
            live_responses=responses,
            warnings=list(dict.fromkeys(warnings)),
            provider_name=gateway.provider_name,
        )


    def rank_candidates(
        self,
        request: DiscoveryRequest,
        candidates: list[CompanyCandidate],
    ) -> list[CompanyCandidate]:
        self._validate_request(request)

        enriched = [
            self._evaluate_candidate(request, candidate)
            for candidate in candidates
        ]

        return sorted(
            enriched,
            key=lambda item: (
                item.verification_status == "Verified",
                item.confidence_score,
                -len(item.risk_flags),
                -len(item.missing_information),
            ),
            reverse=True,
        )

    def candidate_to_partner_payload(
        self,
        candidate: CompanyCandidate,
    ) -> dict[str, Any]:
        evidence = "\n".join(
            f"- {url}" for url in candidate.source_urls
        ) or "- No source links recorded"

        certificates = ", ".join(candidate.certificates) or "Not recorded"
        risks = ", ".join(candidate.risk_flags) or "None recorded"
        missing = (
            ", ".join(candidate.missing_information)
            or "No major gaps recorded"
        )

        notes = (
            f"Discovery confidence: {candidate.confidence_score}/100\n"
            f"Verification status: {candidate.verification_status}\n"
            f"Certificates: {certificates}\n"
            f"MOQ: {candidate.moq or 'Not recorded'}\n"
            f"Price: {candidate.price_information or 'Not recorded'}\n"
            f"Incoterms: {candidate.incoterms or 'Not recorded'}\n"
            f"Lead time: {candidate.lead_time or 'Not recorded'}\n"
            f"Payment terms: {candidate.payment_terms or 'Not recorded'}\n"
            f"Packaging: {candidate.packaging or 'Not recorded'}\n"
            f"Private label: {candidate.private_label or 'Not recorded'}\n"
            f"Capacity: {candidate.production_capacity or 'Not recorded'}\n"
            f"Export markets: {candidate.export_markets or 'Not recorded'}\n"
            f"Samples: {candidate.samples or 'Not recorded'}\n"
            f"Risk flags: {risks}\n"
            f"Missing information: {missing}\n\n"
            f"Sources:\n{evidence}\n\n"
            f"{candidate.notes}".strip()
        )

        return {
            "company_name": candidate.company_name,
            "partner_type": candidate.partner_type,
            "country": candidate.country,
            "city": candidate.city,
            "contact_name": candidate.contact_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "whatsapp": candidate.whatsapp,
            "website": candidate.website,
            "products_services": candidate.products_services,
            "status": "Prospect",
            "verification_status": candidate.verification_status,
            "rating": 0,
            "notes": notes,
        }

    def _evaluate_candidate(
        self,
        request: DiscoveryRequest,
        candidate: CompanyCandidate,
    ) -> CompanyCandidate:
        score = 0
        missing: list[str] = []
        risks = list(candidate.risk_flags)

        checks = {
            "Official website": candidate.website,
            "Contact email": candidate.email,
            "Products or services": candidate.products_services,
            "MOQ": candidate.moq,
            "Incoterms": candidate.incoterms,
            "Lead time": candidate.lead_time,
            "Payment terms": candidate.payment_terms,
            "Packaging": candidate.packaging,
            "Export markets": candidate.export_markets,
            "Certificates": candidate.certificates,
            "Source evidence": candidate.source_urls,
        }

        for label, value in checks.items():
            if value:
                score += 7
            else:
                missing.append(label)

        if candidate.company_registration:
            score += 8

        if candidate.factory_address:
            score += 6

        requested_certificates = {
            item.lower()
            for item in request.required_certificates
        }
        candidate_certificates = {
            item.lower()
            for item in candidate.certificates
        }

        if requested_certificates:
            matched = requested_certificates & candidate_certificates
            score += round(
                15 * len(matched) / len(requested_certificates)
            )

            missing_certificates = (
                requested_certificates - candidate_certificates
            )

            if missing_certificates:
                missing.append(
                    "Required certificates: "
                    + ", ".join(sorted(missing_certificates))
                )

        if candidate.source_urls:
            score += min(8, len(candidate.source_urls) * 2)

        if not candidate.website:
            risks.append("No official website recorded")

        if not candidate.email:
            risks.append("No business email recorded")

        if not candidate.source_urls:
            risks.append("No evidence sources recorded")

        score = max(0, min(100, score - len(risks) * 4))

        candidate.confidence_score = score
        candidate.missing_information = list(
            dict.fromkeys(missing)
        )
        candidate.risk_flags = list(dict.fromkeys(risks))

        if score >= 85 and not candidate.risk_flags:
            candidate.verification_status = "Verified"
        elif score >= 65:
            candidate.verification_status = "Partially Verified"
        else:
            candidate.verification_status = "Unverified"

        return candidate

    @staticmethod
    def _validate_request(request: DiscoveryRequest) -> None:
        if request.partner_type not in SUPPORTED_PARTNER_TYPES:
            raise ValueError("Unsupported partner type.")

        if not request.product.strip():
            raise ValueError("Product or service is required.")

        if not 0 <= request.minimum_confidence_score <= 100:
            raise ValueError(
                "Minimum confidence score must be between 0 and 100."
            )

        if (
            request.maximum_lead_time_days is not None
            and request.maximum_lead_time_days <= 0
        ):
            raise ValueError(
                "Maximum lead time must be greater than zero."
            )

    @staticmethod
    def _build_search_queries(
        request: DiscoveryRequest,
    ) -> list[str]:
        location = request.country.strip() or "global"

        base = (
            f"{request.product.strip()} "
            f"{request.partner_type.lower()} {location}"
        )

        queries = [
            f"{base} official company website",
            f"{base} manufacturer exporter contact",
            f"{base} product catalogue MOQ Incoterms",
            f"{base} certificates factory export markets",
            f"{base} business registration trade directory",
        ]

        for certificate in request.required_certificates:
            queries.append(
                f"{base} {certificate} certified"
            )

        if request.destination.strip():
            queries.append(
                f"{base} export to {request.destination.strip()}"
            )

        return list(dict.fromkeys(queries))


_service = GlobalDiscoveryService()


def prepare_discovery_search(
    request: DiscoveryRequest,
) -> DiscoveryResult:
    return _service.prepare_search(request)


def rank_discovery_candidates(
    request: DiscoveryRequest,
    candidates: list[CompanyCandidate],
) -> list[CompanyCandidate]:
    return _service.rank_candidates(request, candidates)


def candidate_to_partner_payload(
    candidate: CompanyCandidate,
) -> dict[str, Any]:
    return _service.candidate_to_partner_payload(candidate)