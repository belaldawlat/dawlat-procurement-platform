"""
Executive Intelligence Engine.

Generates the CEO daily brief and enterprise health view for the Dawlat AI
Procurement & Global Trade Intelligence Platform.

This engine:
- reads grounded platform data;
- prioritises operational and commercial issues;
- summarizes opportunities, risks, payments, shipments and quotations;
- produces explainable recommendations;
- never executes legal, commercial or financial actions automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from services.ai_assistant_service import build_ai_context


@dataclass(frozen=True)
class ExecutiveAlert:
    severity: str
    category: str
    title: str
    description: str
    owner_role: str
    record_id: int | None = None


@dataclass(frozen=True)
class ExecutivePriority:
    rank: int
    title: str
    action: str
    reason: str
    owner_role: str
    urgency: str
    approval_required: bool = False
    expected_value: float | None = None
    currency: str = "AUD"


@dataclass(frozen=True)
class ExecutiveHealthScore:
    overall: int
    commercial: int
    financial: int
    supply: int
    demand: int
    operations: int
    risk: int
    compliance: int
    relationship: int
    ai_confidence: int


@dataclass
class ExecutiveDailyBrief:
    greeting: str
    executive_summary: str
    health: ExecutiveHealthScore
    priorities: list[ExecutivePriority] = field(default_factory=list)
    alerts: list[ExecutiveAlert] = field(default_factory=list)
    opportunity_radar: list[dict[str, Any]] = field(default_factory=list)
    shipment_watch: list[dict[str, Any]] = field(default_factory=list)
    quotation_watch: list[dict[str, Any]] = field(default_factory=list)
    buyer_watch: list[dict[str, Any]] = field(default_factory=list)
    supplier_watch: list[dict[str, Any]] = field(default_factory=list)
    financial_summary: dict[str, Any] = field(default_factory=dict)
    strategic_insights: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ExecutiveIntelligenceEngine:
    """Create one prioritised executive view across the whole platform."""

    def generate_daily_brief(
        self,
        *,
        executive_name: str = "Belal",
    ) -> ExecutiveDailyBrief:
        context = build_ai_context(limit_per_domain=200)

        opportunities = context.get("opportunities", [])
        customers = context.get("customers", [])
        suppliers = context.get("suppliers", [])
        supplier_quotes = context.get("supplier_quotes", [])
        logistics_quotes = context.get("logistics_quotes", [])
        landed_costs = context.get("landed_costs", [])
        shipments = context.get("shipments", [])
        inventory = context.get("inventory", [])

        quotation_watch = self._quotation_watch(supplier_quotes)
        shipment_watch = self._shipment_watch(shipments)
        buyer_watch = self._buyer_watch(customers)
        supplier_watch = self._supplier_watch(suppliers)
        opportunity_radar = self._opportunity_radar(opportunities, landed_costs)
        financial_summary = self._financial_summary(
            opportunities=opportunities,
            landed_costs=landed_costs,
            supplier_quotes=supplier_quotes,
            logistics_quotes=logistics_quotes,
        )

        alerts = self._alerts(
            quotation_watch=quotation_watch,
            shipment_watch=shipment_watch,
            buyer_watch=buyer_watch,
            supplier_watch=supplier_watch,
            inventory=inventory,
        )

        priorities = self._priorities(
            alerts=alerts,
            opportunity_radar=opportunity_radar,
            financial_summary=financial_summary,
        )

        health = self._health_score(
            opportunities=opportunities,
            customers=customers,
            suppliers=suppliers,
            supplier_quotes=supplier_quotes,
            landed_costs=landed_costs,
            shipments=shipments,
            inventory=inventory,
            alerts=alerts,
        )

        strategic_insights = self._strategic_insights(
            opportunities=opportunities,
            suppliers=suppliers,
            customers=customers,
            shipments=shipments,
            landed_costs=landed_costs,
        )

        summary = (
            f"The platform health score is {health.overall}/100. "
            f"There are {len(priorities)} priority action(s), "
            f"{len(alerts)} active alert(s), "
            f"{len(opportunity_radar)} ranked opportunity record(s), and "
            f"{len(shipment_watch)} shipment item(s) requiring monitoring."
        )

        return ExecutiveDailyBrief(
            greeting=self._greeting(executive_name),
            executive_summary=summary,
            health=health,
            priorities=priorities,
            alerts=alerts,
            opportunity_radar=opportunity_radar,
            shipment_watch=shipment_watch,
            quotation_watch=quotation_watch,
            buyer_watch=buyer_watch,
            supplier_watch=supplier_watch,
            financial_summary=financial_summary,
            strategic_insights=strategic_insights,
        )

    @staticmethod
    def _quotation_watch(
        quotes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        today = date.today()
        watched = []

        for item in quotes:
            expiry = _parse_date(item.get("quotation_valid_until"))
            days_remaining = (
                (expiry - today).days
                if expiry
                else None
            )

            if days_remaining is None or days_remaining <= 14:
                watched.append(
                    {
                        "id": item.get("id"),
                        "supplier_name": item.get("supplier_name"),
                        "currency": item.get("currency"),
                        "unit_price": _number(item.get("unit_price")),
                        "lead_time_days": int(
                            _number(item.get("lead_time_days"))
                        ),
                        "valid_until": (
                            expiry.isoformat()
                            if expiry
                            else None
                        ),
                        "days_remaining": days_remaining,
                        "status": item.get("status"),
                    }
                )

        watched.sort(
            key=lambda item: (
                item["days_remaining"]
                if item["days_remaining"] is not None
                else 9999
            )
        )
        return watched[:20]

    @staticmethod
    def _shipment_watch(
        shipments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        today = date.today()
        watched = []

        for item in shipments:
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
            overdue = bool(
                eta
                and eta < today
                and not terminal
            )
            delayed = bool(
                status in {
                    "Delayed",
                    "Biosecurity Hold",
                    "Inspection Hold",
                }
                or item.get("delay_reason")
                or _number(item.get("delay_days")) > 0
                or overdue
            )

            if not terminal or delayed:
                watched.append(
                    {
                        "id": item.get("id"),
                        "shipment": (
                            item.get("shipment_number")
                            or item.get("shipment_reference")
                        ),
                        "product": item.get("product_name"),
                        "supplier": item.get("supplier_name"),
                        "status": status,
                        "eta": (
                            eta.isoformat()
                            if eta
                            else None
                        ),
                        "overdue": overdue,
                        "delayed": delayed,
                        "delay_reason": item.get("delay_reason"),
                        "risk_level": item.get("risk_level"),
                        "priority": item.get("priority"),
                    }
                )

        watched.sort(
            key=lambda item: (
                not item["delayed"],
                item["eta"] or "9999-12-31",
            )
        )
        return watched[:20]

    @staticmethod
    def _buyer_watch(
        customers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        watched = []

        for item in customers:
            lead_status = item.get("lead_status") or ""
            credit_status = item.get("credit_status") or ""

            if lead_status in {
                "Prospect",
                "Contacted",
                "Qualified",
                "Quotation Sent",
            }:
                watched.append(
                    {
                        "id": item.get("id"),
                        "company_name": item.get("company_name"),
                        "lead_status": lead_status,
                        "credit_status": credit_status,
                        "products_of_interest": (
                            item.get("products_of_interest")
                        ),
                        "estimated_demand": item.get("estimated_demand"),
                    }
                )

        return watched[:20]

    @staticmethod
    def _supplier_watch(
        suppliers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        watched = []

        for item in suppliers:
            verification = (
                item.get("verification_status")
                or "Unverified"
            )

            if verification != "Verified":
                watched.append(
                    {
                        "id": item.get("id"),
                        "company_name": item.get("company_name"),
                        "country": item.get("country"),
                        "category": item.get("category"),
                        "verification_status": verification,
                    }
                )

        return watched[:20]

    @staticmethod
    def _opportunity_radar(
        opportunities: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        margins_by_product = {}

        for item in landed_costs:
            product = (
                item.get("product_name")
                or ""
            ).strip().lower()

            if product:
                margins_by_product.setdefault(product, []).append(
                    _number(item.get("gross_margin_percent"))
                )

        ranked = []

        for item in opportunities:
            demand = _number(item.get("demand_score"))
            confidence = _number(item.get("confidence_score"))
            competition = _number(item.get("competition_score"))
            urgency = {
                "Low": 0,
                "Medium": 5,
                "High": 10,
                "Critical": 15,
            }.get(item.get("urgency"), 0)

            product = (
                item.get("product")
                or ""
            ).strip().lower()

            margin_values = margins_by_product.get(product, [])
            average_margin = (
                sum(margin_values) / len(margin_values)
                if margin_values
                else 0
            )

            score = round(
                demand * 0.35
                + confidence * 0.30
                + (100 - competition) * 0.20
                + min(15, max(0, average_margin)) * 0.15
                + urgency
            )

            ranked.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "product": item.get("product"),
                    "buyer_company": item.get("buyer_company"),
                    "country": item.get("country"),
                    "urgency": item.get("urgency"),
                    "status": item.get("status"),
                    "expected_margin": item.get("expected_margin"),
                    "average_recorded_margin": round(
                        average_margin,
                        2,
                    ),
                    "executive_score": max(
                        0,
                        min(100, score),
                    ),
                }
            )

        ranked.sort(
            key=lambda item: item["executive_score"],
            reverse=True,
        )
        return ranked[:20]

    @staticmethod
    def _financial_summary(
        *,
        opportunities: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
        supplier_quotes: list[dict[str, Any]],
        logistics_quotes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        expected_revenue = sum(
            _number(item.get("expected_revenue"))
            for item in landed_costs
        )
        gross_profit = sum(
            _number(item.get("gross_profit"))
            for item in landed_costs
        )
        average_margin = _average(
            [
                _number(item.get("gross_margin_percent"))
                for item in landed_costs
                if item.get("gross_margin_percent") is not None
            ]
        )
        supplier_commitment = sum(
            _number(item.get("unit_price"))
            * _number(item.get("quantity"))
            for item in supplier_quotes
        )
        logistics_commitment = sum(
            _number(item.get("freight_cost"))
            + _number(item.get("customs_clearance_fee"))
            + _number(item.get("local_delivery_fee"))
            for item in logistics_quotes
        )

        return {
            "expected_revenue": round(expected_revenue, 2),
            "expected_gross_profit": round(gross_profit, 2),
            "average_margin_percent": round(average_margin, 2),
            "supplier_quote_value": round(
                supplier_commitment,
                2,
            ),
            "logistics_quote_value": round(
                logistics_commitment,
                2,
            ),
            "opportunity_count": len(opportunities),
            "landed_cost_count": len(landed_costs),
            "currency": "AUD",
        }

    @staticmethod
    def _alerts(
        *,
        quotation_watch: list[dict[str, Any]],
        shipment_watch: list[dict[str, Any]],
        buyer_watch: list[dict[str, Any]],
        supplier_watch: list[dict[str, Any]],
        inventory: list[dict[str, Any]],
    ) -> list[ExecutiveAlert]:
        alerts = []

        for item in quotation_watch:
            days = item.get("days_remaining")

            if days is None:
                alerts.append(
                    ExecutiveAlert(
                        severity="Medium",
                        category="Quotation",
                        title="Quotation validity missing",
                        description=(
                            f"{item.get('supplier_name') or 'Supplier'} "
                            "quotation has no expiry date."
                        ),
                        owner_role="Procurement Specialist",
                        record_id=item.get("id"),
                    )
                )
            elif days < 0:
                alerts.append(
                    ExecutiveAlert(
                        severity="Critical",
                        category="Quotation",
                        title="Supplier quotation expired",
                        description=(
                            f"{item.get('supplier_name') or 'Supplier'} "
                            f"quotation expired {abs(days)} day(s) ago."
                        ),
                        owner_role="Procurement Specialist",
                        record_id=item.get("id"),
                    )
                )
            elif days <= 3:
                alerts.append(
                    ExecutiveAlert(
                        severity="High",
                        category="Quotation",
                        title="Supplier quotation expiring",
                        description=(
                            f"{item.get('supplier_name') or 'Supplier'} "
                            f"quotation expires in {days} day(s)."
                        ),
                        owner_role="Procurement Specialist",
                        record_id=item.get("id"),
                    )
                )

        for item in shipment_watch:
            if item.get("delayed"):
                alerts.append(
                    ExecutiveAlert(
                        severity="Critical",
                        category="Shipment",
                        title="Shipment requires attention",
                        description=(
                            f"{item.get('shipment') or 'Shipment'}: "
                            f"{item.get('delay_reason') or item.get('status')}"
                        ),
                        owner_role="Logistics Coordinator",
                        record_id=item.get("id"),
                    )
                )

        if buyer_watch:
            alerts.append(
                ExecutiveAlert(
                    severity="Medium",
                    category="Buyer",
                    title="Buyer follow-up queue",
                    description=(
                        f"{len(buyer_watch)} buyer record(s) "
                        "require qualification or follow-up."
                    ),
                    owner_role="Customer Acquisition Manager",
                )
            )

        if supplier_watch:
            alerts.append(
                ExecutiveAlert(
                    severity="High",
                    category="Supplier",
                    title="Supplier verification queue",
                    description=(
                        f"{len(supplier_watch)} supplier record(s) "
                        "are not fully verified."
                    ),
                    owner_role="Global Sourcing Specialist",
                )
            )

        low_stock = [
            item
            for item in inventory
            if (
                _number(item.get("quantity_on_hand"))
                - _number(item.get("quantity_reserved"))
            )
            <= _number(item.get("reorder_level"))
        ]

        if low_stock:
            alerts.append(
                ExecutiveAlert(
                    severity="High",
                    category="Inventory",
                    title="Low inventory",
                    description=(
                        f"{len(low_stock)} inventory item(s) "
                        "require reorder review."
                    ),
                    owner_role="Inventory Manager",
                )
            )

        return alerts

    @staticmethod
    def _priorities(
        *,
        alerts: list[ExecutiveAlert],
        opportunity_radar: list[dict[str, Any]],
        financial_summary: dict[str, Any],
    ) -> list[ExecutivePriority]:
        priorities = []

        severity_rank = {
            "Critical": 1,
            "High": 2,
            "Medium": 3,
            "Low": 4,
        }

        for alert in alerts:
            priorities.append(
                ExecutivePriority(
                    rank=severity_rank.get(alert.severity, 4),
                    title=alert.title,
                    action=alert.description,
                    reason=(
                        f"{alert.category} alert requires attention."
                    ),
                    owner_role=alert.owner_role,
                    urgency=alert.severity,
                    approval_required=(
                        alert.severity == "Critical"
                    ),
                )
            )

        if opportunity_radar:
            top = opportunity_radar[0]
            priorities.append(
                ExecutivePriority(
                    rank=2,
                    title="Highest-ranked opportunity",
                    action=(
                        f"Review {top.get('title') or 'the top opportunity'}."
                    ),
                    reason=(
                        f"Executive opportunity score: "
                        f"{top.get('executive_score')}/100."
                    ),
                    owner_role="Executive Advisor",
                    urgency="High",
                    approval_required=True,
                    expected_value=(
                        financial_summary.get(
                            "expected_gross_profit"
                        )
                    ),
                    currency=financial_summary.get(
                        "currency",
                        "AUD",
                    ),
                )
            )

        priorities.sort(
            key=lambda item: (
                item.rank,
                not item.approval_required,
            )
        )

        return [
            ExecutivePriority(
                rank=index,
                title=item.title,
                action=item.action,
                reason=item.reason,
                owner_role=item.owner_role,
                urgency=item.urgency,
                approval_required=item.approval_required,
                expected_value=item.expected_value,
                currency=item.currency,
            )
            for index, item in enumerate(
                priorities[:15],
                start=1,
            )
        ]

    @staticmethod
    def _health_score(
        *,
        opportunities: list[dict[str, Any]],
        customers: list[dict[str, Any]],
        suppliers: list[dict[str, Any]],
        supplier_quotes: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
        shipments: list[dict[str, Any]],
        inventory: list[dict[str, Any]],
        alerts: list[ExecutiveAlert],
    ) -> ExecutiveHealthScore:
        critical = sum(
            1 for item in alerts
            if item.severity == "Critical"
        )
        high = sum(
            1 for item in alerts
            if item.severity == "High"
        )

        commercial = _score(
            50
            + min(25, len(supplier_quotes) * 3)
            + min(25, len(landed_costs) * 4)
            - critical * 8
        )
        financial = _score(
            45
            + min(35, len(landed_costs) * 5)
            - high * 4
        )
        supply = _score(
            40
            + min(35, len(suppliers) * 3)
            + min(25, len(supplier_quotes) * 2)
        )
        demand = _score(
            40
            + min(30, len(customers) * 3)
            + min(30, len(opportunities) * 3)
        )
        operations = _score(
            80
            - critical * 12
            - high * 6
            + min(10, len(shipments))
        )
        risk = _score(
            100
            - critical * 15
            - high * 8
        )
        compliance = _score(
            85
            - sum(
                8
                for item in alerts
                if item.category in {
                    "Supplier",
                    "Quotation",
                }
            )
        )
        relationship = _score(
            50
            + min(25, len(customers) * 3)
            + min(25, len(suppliers) * 2)
        )
        ai_confidence = _score(
            35
            + min(
                65,
                (
                    len(opportunities)
                    + len(customers)
                    + len(suppliers)
                    + len(supplier_quotes)
                    + len(landed_costs)
                    + len(shipments)
                    + len(inventory)
                )
                * 2,
            )
        )

        values = [
            commercial,
            financial,
            supply,
            demand,
            operations,
            risk,
            compliance,
            relationship,
            ai_confidence,
        ]

        return ExecutiveHealthScore(
            overall=round(sum(values) / len(values)),
            commercial=commercial,
            financial=financial,
            supply=supply,
            demand=demand,
            operations=operations,
            risk=risk,
            compliance=compliance,
            relationship=relationship,
            ai_confidence=ai_confidence,
        )

    @staticmethod
    def _strategic_insights(
        *,
        opportunities: list[dict[str, Any]],
        suppliers: list[dict[str, Any]],
        customers: list[dict[str, Any]],
        shipments: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
    ) -> list[str]:
        insights = []

        if opportunities and not customers:
            insights.append(
                "Market opportunities exist, but verified buyer demand is not yet recorded."
            )

        if customers and not suppliers:
            insights.append(
                "Buyer demand exists, but the platform lacks verified matching suppliers."
            )

        if suppliers and not landed_costs:
            insights.append(
                "Supplier options exist, but commercial viability is not confirmed by landed-cost analysis."
            )

        delayed = [
            item
            for item in shipments
            if (
                item.get("shipment_status")
                or item.get("status")
            )
            in {
                "Delayed",
                "Biosecurity Hold",
                "Inspection Hold",
            }
            or item.get("delay_reason")
        ]

        if delayed:
            insights.append(
                "Historical shipment exceptions should influence future carrier, route and supplier scoring."
            )

        if not insights:
            insights.append(
                "Continue strengthening buyer verification, supplier verification and completed-deal history."
            )

        return insights

    @staticmethod
    def _greeting(name: str) -> str:
        hour = datetime.now().hour

        if hour < 12:
            period = "Good morning"
        elif hour < 18:
            period = "Good afternoon"
        else:
            period = "Good evening"

        return f"{period}, {name}."


def _parse_date(value: Any) -> date | None:
    if not value:
        return None

    try:
        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _score(value: float) -> int:
    return max(0, min(100, round(value)))


_engine = ExecutiveIntelligenceEngine()


def generate_executive_daily_brief(
    *,
    executive_name: str = "Belal",
) -> ExecutiveDailyBrief:
    """Public executive-intelligence entry point."""

    return _engine.generate_daily_brief(
        executive_name=executive_name,
    )