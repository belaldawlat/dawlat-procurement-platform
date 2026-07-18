"""
Opportunity Intelligence Engine.

Identifies and ranks trade opportunities by matching verified demand with
available local or international supply.

The engine is read-only and evidence-driven. It does not contact buyers,
commit suppliers, issue quotations, release payments or create orders
automatically. Binding actions remain subject to human approval and the
Enterprise Decision Engine.

Core questions:
- What does the market need?
- Is the demand verified?
- Who can fulfil it locally or internationally?
- What evidence is missing?
- Is the opportunity commercially attractive?
- What should Dawlat Global do next?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.ai_assistant_service import build_ai_context
from services.global_discovery_service import (
    DiscoveryRequest,
    prepare_discovery_search,
)
from services.supplier_ranking_engine import (
    RankedSupplierResult,
    rank_supplier_results,
)


@dataclass(frozen=True)
class DemandSignal:
    source_type: str
    source_id: int | None
    buyer_name: str
    product: str
    quantity: float | None
    unit: str
    destination: str
    target_price: float | None
    currency: str
    required_date: str | None
    confidence_score: int
    verified: bool
    evidence_summary: str


@dataclass(frozen=True)
class SupplyOption:
    source_type: str
    source_id: int | None
    supplier_name: str
    country: str
    product: str
    unit_price: float | None
    currency: str
    lead_time_days: int | None
    incoterm: str
    verification_status: str
    overall_score: int
    local_supply: bool
    live_source_url: str | None = None
    evidence_summary: str = ""


@dataclass(frozen=True)
class OpportunityGap:
    gap_type: str
    description: str
    severity: str
    blocking: bool
    recommended_resolution: str


@dataclass(frozen=True)
class OpportunityRecommendation:
    priority: int
    action: str
    owner_role: str
    reason: str
    approval_required: bool = False
    expected_value: float | None = None
    currency: str = "AUD"


@dataclass
class OpportunityAssessment:
    title: str
    product: str
    destination: str
    opportunity_score: int
    demand_score: int
    supply_score: int
    commercial_score: int
    confidence_score: int
    recommendation_status: str
    executive_summary: str

    demand_signals: list[DemandSignal] = field(default_factory=list)
    local_supply_options: list[SupplyOption] = field(default_factory=list)
    international_supply_options: list[SupplyOption] = field(default_factory=list)
    gaps: list[OpportunityGap] = field(default_factory=list)
    recommendations: list[OpportunityRecommendation] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class OpportunityIntelligenceEngine:
    """
    Enterprise opportunity-matching engine.

    It combines saved opportunities, customers, suppliers, quotations,
    landed-cost records and optional live supplier discovery.
    """

    def assess(
        self,
        *,
        product: str,
        destination: str,
        origin_country_preference: str = "",
        buyer_name: str = "",
        include_live_discovery: bool = False,
        required_certificates: tuple[str, ...] = (),
        preferred_incoterms: tuple[str, ...] = (),
        maximum_lead_time_days: int | None = None,
    ) -> OpportunityAssessment:
        self._validate(product, destination)

        context = build_ai_context(limit_per_domain=200)
        terms = self._terms(
            product=product,
            destination=destination,
            buyer_name=buyer_name,
        )

        opportunities = self._match(
            context.get("opportunities", []),
            terms,
            ("title", "product", "buyer_company", "country", "state", "city", "notes"),
        )
        customers = self._match(
            context.get("customers", []),
            terms,
            (
                "company_name",
                "products_of_interest",
                "estimated_demand",
                "country",
                "city",
                "notes",
            ),
        )
        suppliers = self._match(
            context.get("suppliers", []),
            self._terms(product=product, destination="", buyer_name=""),
            ("company_name", "category", "country", "notes"),
        )
        quotes = self._match(
            context.get("supplier_quotes", []),
            self._terms(product=product, destination="", buyer_name=""),
            ("supplier_name", "packaging", "certificates", "notes"),
        )
        landed_costs = self._match(
            context.get("landed_costs", []),
            terms,
            (
                "name",
                "product_name",
                "supplier_name",
                "origin_country",
                "destination",
                "notes",
            ),
        )

        demand_signals = self._demand_signals(
            product=product,
            destination=destination,
            buyer_name=buyer_name,
            opportunities=opportunities,
            customers=customers,
        )

        saved_supply = self._saved_supply_options(
            product=product,
            destination=destination,
            suppliers=suppliers,
            quotes=quotes,
        )

        live_supply: list[SupplyOption] = []

        if include_live_discovery:
            live_supply = self._live_supply_options(
                product=product,
                destination=destination,
                country=origin_country_preference,
                required_certificates=required_certificates,
                preferred_incoterms=preferred_incoterms,
                maximum_lead_time_days=maximum_lead_time_days,
            )

        all_supply = self._deduplicate_supply(
            saved_supply + live_supply
        )

        local_supply = [
            item
            for item in all_supply
            if item.local_supply
        ]
        international_supply = [
            item
            for item in all_supply
            if not item.local_supply
        ]

        demand_score = self._demand_score(demand_signals)
        supply_score = self._supply_score(all_supply)
        commercial_score = self._commercial_score(
            quotes=quotes,
            landed_costs=landed_costs,
        )

        gaps = self._gaps(
            demand_signals=demand_signals,
            supply_options=all_supply,
            landed_costs=landed_costs,
            buyer_name=buyer_name,
        )

        confidence_score = self._confidence_score(
            demand_signals=demand_signals,
            supply_options=all_supply,
            landed_costs=landed_costs,
            gaps=gaps,
        )

        opportunity_score = round(
            demand_score * 0.35
            + supply_score * 0.30
            + commercial_score * 0.25
            + confidence_score * 0.10
        )

        recommendation_status = self._status(
            opportunity_score=opportunity_score,
            gaps=gaps,
            demand_signals=demand_signals,
            supply_options=all_supply,
        )

        recommendations = self._recommendations(
            status=recommendation_status,
            demand_signals=demand_signals,
            local_supply=local_supply,
            international_supply=international_supply,
            landed_costs=landed_costs,
            gaps=gaps,
        )

        evidence = self._evidence(
            opportunities=opportunities,
            customers=customers,
            suppliers=suppliers,
            quotes=quotes,
            landed_costs=landed_costs,
            live_supply=live_supply,
        )

        return OpportunityAssessment(
            title=f"Opportunity Assessment: {product}",
            product=product,
            destination=destination,
            opportunity_score=max(0, min(100, opportunity_score)),
            demand_score=demand_score,
            supply_score=supply_score,
            commercial_score=commercial_score,
            confidence_score=confidence_score,
            recommendation_status=recommendation_status,
            executive_summary=self._summary(
                product=product,
                destination=destination,
                demand_signals=demand_signals,
                local_supply=local_supply,
                international_supply=international_supply,
                opportunity_score=opportunity_score,
                recommendation_status=recommendation_status,
                gaps=gaps,
            ),
            demand_signals=demand_signals,
            local_supply_options=local_supply,
            international_supply_options=international_supply,
            gaps=gaps,
            recommendations=recommendations,
            evidence=evidence,
            assumptions=[
                "Saved records are operational evidence, not independently audited truth.",
                "Live web candidates remain unverified until reviewed and approved.",
                "Buyer readiness, final pricing and cleared funds must be confirmed before supplier commitment.",
                "Profit is not considered protected until a complete landed-cost calculation is approved.",
            ],
        )

    @staticmethod
    def _demand_signals(
        *,
        product: str,
        destination: str,
        buyer_name: str,
        opportunities: list[dict[str, Any]],
        customers: list[dict[str, Any]],
    ) -> list[DemandSignal]:
        signals: list[DemandSignal] = []

        for item in opportunities:
            quantity, unit = _extract_quantity(
                item.get("estimated_quantity")
            )

            signals.append(
                DemandSignal(
                    source_type="Market Opportunity",
                    source_id=item.get("id"),
                    buyer_name=(
                        item.get("buyer_company")
                        or buyer_name
                        or "Unconfirmed Buyer"
                    ),
                    product=item.get("product") or product,
                    quantity=quantity,
                    unit=unit,
                    destination=", ".join(
                        part
                        for part in (
                            item.get("city"),
                            item.get("state"),
                            item.get("country"),
                        )
                        if part
                    )
                    or destination,
                    target_price=_number_or_none(
                        item.get("target_price")
                    ),
                    currency="AUD",
                    required_date=None,
                    confidence_score=int(
                        _number(item.get("confidence_score"))
                    ),
                    verified=bool(item.get("buyer_company")),
                    evidence_summary=(
                        f"Status: {item.get('status') or 'Not recorded'}; "
                        f"demand score: {item.get('demand_score') or 0}; "
                        f"urgency: {item.get('urgency') or 'Not recorded'}."
                    ),
                )
            )

        for item in customers:
            signals.append(
                DemandSignal(
                    source_type="Customer",
                    source_id=item.get("id"),
                    buyer_name=item.get("company_name") or buyer_name or "Customer",
                    product=product,
                    quantity=None,
                    unit="",
                    destination=", ".join(
                        part
                        for part in (
                            item.get("city"),
                            item.get("country"),
                        )
                        if part
                    )
                    or destination,
                    target_price=None,
                    currency="AUD",
                    required_date=None,
                    confidence_score=_buyer_confidence(item),
                    verified=(
                        item.get("lead_status")
                        in {
                            "Qualified",
                            "Quotation Sent",
                            "Accepted",
                            "Customer",
                        }
                    ),
                    evidence_summary=(
                        f"Lead status: {item.get('lead_status') or 'Not recorded'}; "
                        f"credit status: {item.get('credit_status') or 'Not assessed'}; "
                        f"estimated demand: {item.get('estimated_demand') or 'Not recorded'}."
                    ),
                )
            )

        return signals

    @staticmethod
    def _saved_supply_options(
        *,
        product: str,
        destination: str,
        suppliers: list[dict[str, Any]],
        quotes: list[dict[str, Any]],
    ) -> list[SupplyOption]:
        quotes_by_supplier: dict[str, list[dict[str, Any]]] = {}

        for quote in quotes:
            key = (
                quote.get("supplier_name")
                or ""
            ).strip().lower()

            if key:
                quotes_by_supplier.setdefault(key, []).append(
                    quote
                )

        supply: list[SupplyOption] = []

        for supplier in suppliers:
            name = supplier.get("company_name") or "Unknown Supplier"
            key = name.strip().lower()
            supplier_quotes = quotes_by_supplier.get(key, [])

            best_quote = None

            if supplier_quotes:
                valid = [
                    item
                    for item in supplier_quotes
                    if _number(item.get("unit_price")) > 0
                ]

                if valid:
                    best_quote = min(
                        valid,
                        key=lambda item: (
                            _number(item.get("unit_price")),
                            _number(item.get("risk_score")),
                        ),
                    )

            country = supplier.get("country") or ""
            local_supply = _is_australia(country)

            verification = (
                supplier.get("verification_status")
                or "Unverified"
            )

            score = 35
            score += 25 if verification == "Verified" else 0
            score += 15 if best_quote else 0
            score += 10 if local_supply else 0
            score += min(
                15,
                int(_number(supplier.get("rating"))) * 3,
            )

            supply.append(
                SupplyOption(
                    source_type="Saved Supplier",
                    source_id=supplier.get("id"),
                    supplier_name=name,
                    country=country,
                    product=product,
                    unit_price=(
                        _number_or_none(
                            best_quote.get("unit_price")
                        )
                        if best_quote
                        else None
                    ),
                    currency=(
                        best_quote.get("currency")
                        if best_quote
                        else ""
                    )
                    or "Not Recorded",
                    lead_time_days=(
                        int(_number(best_quote.get("lead_time_days")))
                        if best_quote
                        and _number(best_quote.get("lead_time_days")) > 0
                        else None
                    ),
                    incoterm=(
                        best_quote.get("incoterm")
                        if best_quote
                        else ""
                    )
                    or "Not Recorded",
                    verification_status=verification,
                    overall_score=max(0, min(100, score)),
                    local_supply=local_supply,
                    evidence_summary=(
                        f"Saved supplier; destination: {destination}; "
                        f"quotation available: {'Yes' if best_quote else 'No'}."
                    ),
                )
            )

        return supply

    @staticmethod
    def _live_supply_options(
        *,
        product: str,
        destination: str,
        country: str,
        required_certificates: tuple[str, ...],
        preferred_incoterms: tuple[str, ...],
        maximum_lead_time_days: int | None,
    ) -> list[SupplyOption]:
        request = DiscoveryRequest(
            partner_type="Supplier",
            product=product,
            country=country,
            destination=destination,
            requirements=(
                "Manufacturer or exporter with official company website, "
                "business contacts, export capability, packaging, MOQ, "
                "quotation, certificates and delivery capability."
            ),
            required_certificates=required_certificates,
            preferred_incoterms=preferred_incoterms,
            maximum_lead_time_days=maximum_lead_time_days,
            minimum_confidence_score=60,
        )

        result = prepare_discovery_search(request)

        raw_results = [
            item
            for response in result.live_responses
            if response.success
            for item in response.results
        ]

        ranked: list[RankedSupplierResult] = rank_supplier_results(
            raw_results,
            product=product,
            country=country,
            partner_type="Supplier",
        )

        return [
            SupplyOption(
                source_type="Live Discovery",
                source_id=None,
                supplier_name=item.title,
                country=country or "Not Confirmed",
                product=product,
                unit_price=None,
                currency="",
                lead_time_days=None,
                incoterm="Not Confirmed",
                verification_status="Unverified",
                overall_score=item.overall_score,
                local_supply=_is_australia(country),
                live_source_url=item.url,
                evidence_summary=(
                    f"{item.classification}; "
                    f"{item.recommendation}; "
                    f"risk flags: {len(item.risk_flags)}."
                ),
            )
            for item in ranked
            if item.overall_score >= 60
        ][:20]

    @staticmethod
    def _demand_score(
        signals: list[DemandSignal],
    ) -> int:
        if not signals:
            return 0

        verified = sum(
            1
            for item in signals
            if item.verified
        )
        average_confidence = sum(
            item.confidence_score
            for item in signals
        ) / len(signals)

        score = (
            min(40, len(signals) * 10)
            + min(30, verified * 15)
            + min(30, round(average_confidence * 0.30))
        )

        return max(0, min(100, round(score)))

    @staticmethod
    def _supply_score(
        options: list[SupplyOption],
    ) -> int:
        if not options:
            return 0

        top_scores = sorted(
            (
                item.overall_score
                for item in options
            ),
            reverse=True,
        )[:5]

        verified = sum(
            1
            for item in options
            if item.verification_status == "Verified"
        )

        score = (
            sum(top_scores) / len(top_scores) * 0.70
            + min(20, verified * 10)
            + min(10, len(options) * 2)
        )

        return max(0, min(100, round(score)))

    @staticmethod
    def _commercial_score(
        *,
        quotes: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
    ) -> int:
        score = 0

        if quotes:
            score += min(30, len(quotes) * 10)

        valid_costs = [
            item
            for item in landed_costs
            if _number(item.get("landed_cost_per_unit")) > 0
        ]

        if valid_costs:
            score += 35

            positive_margin = [
                item
                for item in valid_costs
                if _number(item.get("gross_margin_percent")) > 0
            ]

            if positive_margin:
                best_margin = max(
                    _number(item.get("gross_margin_percent"))
                    for item in positive_margin
                )
                score += min(35, round(best_margin))

        return max(0, min(100, score))

    @staticmethod
    def _gaps(
        *,
        demand_signals: list[DemandSignal],
        supply_options: list[SupplyOption],
        landed_costs: list[dict[str, Any]],
        buyer_name: str,
    ) -> list[OpportunityGap]:
        gaps: list[OpportunityGap] = []

        if not demand_signals:
            gaps.append(
                OpportunityGap(
                    gap_type="Demand",
                    description="No saved buyer demand or market opportunity is confirmed.",
                    severity="Critical",
                    blocking=True,
                    recommended_resolution=(
                        "Verify an Australian buyer, exact requirement, quantity, "
                        "delivery date and purchase readiness."
                    ),
                )
            )

        elif not any(item.verified for item in demand_signals):
            gaps.append(
                OpportunityGap(
                    gap_type="Demand Verification",
                    description="Demand exists, but buyer readiness is not verified.",
                    severity="High",
                    blocking=True,
                    recommended_resolution=(
                        "Qualify the buyer and obtain written confirmation of requirements."
                    ),
                )
            )

        if buyer_name and not any(
            item.buyer_name.lower() == buyer_name.lower()
            for item in demand_signals
        ):
            gaps.append(
                OpportunityGap(
                    gap_type="Buyer Link",
                    description="The named buyer is not linked to a matching saved demand record.",
                    severity="High",
                    blocking=True,
                    recommended_resolution="Create or link the verified buyer requirement.",
                )
            )

        if not supply_options:
            gaps.append(
                OpportunityGap(
                    gap_type="Supply",
                    description="No local or international supply option is available.",
                    severity="Critical",
                    blocking=True,
                    recommended_resolution="Run global and local supplier discovery.",
                )
            )

        elif not any(
            item.verification_status == "Verified"
            for item in supply_options
        ):
            gaps.append(
                OpportunityGap(
                    gap_type="Supplier Verification",
                    description="Supply candidates exist, but none are fully verified.",
                    severity="High",
                    blocking=True,
                    recommended_resolution=(
                        "Verify legal identity, factory, capacity, certificates, "
                        "contacts and bank details."
                    ),
                )
            )

        if not landed_costs:
            gaps.append(
                OpportunityGap(
                    gap_type="Commercial",
                    description="No completed landed-cost calculation is available.",
                    severity="Critical",
                    blocking=True,
                    recommended_resolution=(
                        "Calculate full landed cost, selling price, contingency and margin."
                    ),
                )
            )

        return gaps

    @staticmethod
    def _confidence_score(
        *,
        demand_signals: list[DemandSignal],
        supply_options: list[SupplyOption],
        landed_costs: list[dict[str, Any]],
        gaps: list[OpportunityGap],
    ) -> int:
        score = 10
        score += min(30, len(demand_signals) * 10)
        score += min(30, len(supply_options) * 5)
        score += 20 if landed_costs else 0
        score += 10 if any(
            item.verification_status == "Verified"
            for item in supply_options
        ) else 0
        score -= sum(
            15 if item.blocking else 5
            for item in gaps
        )

        return max(0, min(100, score))

    @staticmethod
    def _status(
        *,
        opportunity_score: int,
        gaps: list[OpportunityGap],
        demand_signals: list[DemandSignal],
        supply_options: list[SupplyOption],
    ) -> str:
        if any(item.blocking for item in gaps):
            return "Research and Verification Required"
        if not demand_signals or not supply_options:
            return "Insufficient Evidence"
        if opportunity_score >= 80:
            return "High-Priority Opportunity"
        if opportunity_score >= 60:
            return "Promising Opportunity"
        if opportunity_score >= 40:
            return "Conditional Opportunity"
        return "Low-Priority Opportunity"

    @staticmethod
    def _recommendations(
        *,
        status: str,
        demand_signals: list[DemandSignal],
        local_supply: list[SupplyOption],
        international_supply: list[SupplyOption],
        landed_costs: list[dict[str, Any]],
        gaps: list[OpportunityGap],
    ) -> list[OpportunityRecommendation]:
        actions: list[OpportunityRecommendation] = []
        priority = 1

        for gap in gaps:
            actions.append(
                OpportunityRecommendation(
                    priority=priority,
                    action=gap.recommended_resolution,
                    owner_role=_owner_for_gap(gap.gap_type),
                    reason=gap.description,
                    approval_required=gap.blocking,
                )
            )
            priority += 1

        if demand_signals and not any(
            item.verified
            for item in demand_signals
        ):
            actions.append(
                OpportunityRecommendation(
                    priority=priority,
                    action=(
                        "Contact the highest-potential buyer and confirm final "
                        "product, quantity, price, delivery date and payment readiness."
                    ),
                    owner_role="Customer Acquisition Manager",
                    reason="Demand must be commercially verified before supplier commitment.",
                    approval_required=False,
                )
            )
            priority += 1

        if local_supply:
            top_local = max(
                local_supply,
                key=lambda item: item.overall_score,
            )
            actions.append(
                OpportunityRecommendation(
                    priority=priority,
                    action=f"Review local supply option: {top_local.supplier_name}.",
                    owner_role="Procurement Specialist",
                    reason=(
                        "Local fulfilment may reduce lead time, import risk and working capital."
                    ),
                    approval_required=True,
                )
            )
            priority += 1

        if international_supply:
            top_global = max(
                international_supply,
                key=lambda item: item.overall_score,
            )
            actions.append(
                OpportunityRecommendation(
                    priority=priority,
                    action=(
                        f"Verify and request a structured quotation from "
                        f"{top_global.supplier_name}."
                    ),
                    owner_role="Global Sourcing Specialist",
                    reason=(
                        f"Highest-ranked international supply score: "
                        f"{top_global.overall_score}/100."
                    ),
                    approval_required=True,
                )
            )
            priority += 1

        if landed_costs and status in {
            "High-Priority Opportunity",
            "Promising Opportunity",
        }:
            best = min(
                landed_costs,
                key=lambda item: _number(
                    item.get("landed_cost_per_unit")
                )
                or float("inf"),
            )

            actions.append(
                OpportunityRecommendation(
                    priority=priority,
                    action=(
                        "Prepare the controlled buyer quotation using the "
                        "best approved landed-cost scenario."
                    ),
                    owner_role="Commercial Manager",
                    reason=(
                        f"Recorded landed cost per unit: "
                        f"{_number(best.get('landed_cost_per_unit')):,.2f}."
                    ),
                    approval_required=True,
                    expected_value=_number_or_none(
                        best.get("gross_profit")
                    ),
                    currency=(
                        best.get("reporting_currency")
                        or "AUD"
                    ),
                )
            )

        return actions

    @staticmethod
    def _summary(
        *,
        product: str,
        destination: str,
        demand_signals: list[DemandSignal],
        local_supply: list[SupplyOption],
        international_supply: list[SupplyOption],
        opportunity_score: int,
        recommendation_status: str,
        gaps: list[OpportunityGap],
    ) -> str:
        return (
            f"{product} opportunity for {destination}: "
            f"{len(demand_signals)} demand signal(s), "
            f"{len(local_supply)} local supply option(s), "
            f"{len(international_supply)} international supply option(s), "
            f"{len(gaps)} material gap(s). "
            f"Opportunity score: {max(0, min(100, opportunity_score))}/100. "
            f"Status: {recommendation_status}."
        )

    @staticmethod
    def _evidence(
        *,
        opportunities: list[dict[str, Any]],
        customers: list[dict[str, Any]],
        suppliers: list[dict[str, Any]],
        quotes: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
        live_supply: list[SupplyOption],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []

        groups = (
            ("Market Opportunity", opportunities, "title"),
            ("Customer", customers, "company_name"),
            ("Supplier", suppliers, "company_name"),
            ("Supplier Quotation", quotes, "supplier_name"),
            ("Landed Cost", landed_costs, "name"),
        )

        for source, records, label_field in groups:
            for item in records[:5]:
                evidence.append(
                    {
                        "source": source,
                        "record_id": item.get("id"),
                        "label": item.get(label_field) or source,
                        "details": str(item)[:500],
                    }
                )

        for item in live_supply[:5]:
            evidence.append(
                {
                    "source": "Live Discovery",
                    "record_id": None,
                    "label": item.supplier_name,
                    "url": item.live_source_url,
                    "details": item.evidence_summary,
                }
            )

        return evidence

    @staticmethod
    def _deduplicate_supply(
        options: list[SupplyOption],
    ) -> list[SupplyOption]:
        unique: dict[str, SupplyOption] = {}

        for item in options:
            key = (
                item.supplier_name.strip().lower()
                or item.live_source_url
                or str(item.source_id)
            )

            current = unique.get(key)

            if current is None or item.overall_score > current.overall_score:
                unique[key] = item

        return sorted(
            unique.values(),
            key=lambda item: item.overall_score,
            reverse=True,
        )

    @staticmethod
    def _validate(
        product: str,
        destination: str,
    ) -> None:
        if not product.strip():
            raise ValueError("Product is required.")
        if not destination.strip():
            raise ValueError("Destination is required.")

    @staticmethod
    def _terms(
        *,
        product: str,
        destination: str,
        buyer_name: str,
    ) -> list[str]:
        terms = []

        for value in (
            product,
            destination,
            buyer_name,
        ):
            terms.extend(
                token
                for token in (
                    value.lower()
                    .replace(",", " ")
                    .replace("-", " ")
                    .split()
                )
                if len(token) >= 3
            )

        return list(dict.fromkeys(terms))

    @staticmethod
    def _match(
        records: list[dict[str, Any]],
        terms: list[str],
        fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if not terms:
            return records

        matched = []

        for record in records:
            haystack = " ".join(
                str(record.get(field) or "")
                for field in fields
            ).lower()

            if any(term in haystack for term in terms):
                matched.append(record)

        return matched


def _buyer_confidence(
    customer: dict[str, Any],
) -> int:
    score = 20

    lead_status = customer.get("lead_status")

    score += {
        "Prospect": 5,
        "Contacted": 15,
        "Qualified": 30,
        "Quotation Sent": 40,
        "Accepted": 55,
        "Customer": 60,
    }.get(lead_status, 0)

    if customer.get("credit_status") in {
        "Approved",
        "Good",
        "Assessed",
    }:
        score += 20

    return max(0, min(100, score))


def _extract_quantity(
    value: Any,
) -> tuple[float | None, str]:
    if value in (None, ""):
        return None, ""

    text = str(value).strip()
    parts = text.replace(",", "").split()

    try:
        quantity = float(parts[0])
    except (ValueError, IndexError):
        return None, text

    unit = " ".join(parts[1:])
    return quantity, unit


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _number_or_none(
    value: Any,
) -> float | None:
    number = _number(value)
    return number if number != 0 else None


def _is_australia(
    country: str,
) -> bool:
    normalized = country.strip().lower()
    return normalized in {
        "australia",
        "au",
        "aus",
    }


def _owner_for_gap(
    gap_type: str,
) -> str:
    return {
        "Demand": "Market Intelligence Manager",
        "Demand Verification": "Customer Acquisition Manager",
        "Buyer Link": "Sales Manager",
        "Supply": "Global Sourcing Specialist",
        "Supplier Verification": "Compliance Manager",
        "Commercial": "Cost & Profit Analyst",
    }.get(gap_type, "Executive Advisor")


_engine = OpportunityIntelligenceEngine()


def assess_trade_opportunity(
    *,
    product: str,
    destination: str,
    origin_country_preference: str = "",
    buyer_name: str = "",
    include_live_discovery: bool = False,
    required_certificates: tuple[str, ...] = (),
    preferred_incoterms: tuple[str, ...] = (),
    maximum_lead_time_days: int | None = None,
) -> OpportunityAssessment:
    """Public opportunity-intelligence entry point."""

    return _engine.assess(
        product=product,
        destination=destination,
        origin_country_preference=origin_country_preference,
        buyer_name=buyer_name,
        include_live_discovery=include_live_discovery,
        required_certificates=required_certificates,
        preferred_incoterms=preferred_incoterms,
        maximum_lead_time_days=maximum_lead_time_days,
    )