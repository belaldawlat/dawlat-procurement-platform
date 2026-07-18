"""Supplier portfolio command and concentration intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class SupplierPortfolioTier(str, Enum):
    STRATEGIC = "Strategic"
    PREFERRED = "Preferred"
    APPROVED = "Approved"
    CONDITIONAL = "Conditional"
    RESTRICTED = "Restricted"
    BLOCKED = "Blocked"


@dataclass(frozen=True)
class SupplierPortfolioInput:
    supplier_id: str
    supplier_name: str
    country: str
    category: str
    annual_spend: float
    quality_score: int
    delivery_score: int
    price_score: int
    responsiveness_score: int
    compliance_score: int
    capacity_score: int
    dispute_count: int
    documents_complete: bool
    sanctions_clear: bool
    approved: bool
    active: bool
    backup_supplier_count: int


@dataclass(frozen=True)
class SupplierPortfolioRecord:
    supplier_id: str
    supplier_name: str
    country: str
    category: str
    tier: SupplierPortfolioTier
    composite_score: int
    annual_spend: float
    concentration_percent: float
    backup_coverage: bool
    warnings: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class SupplierPortfolioSnapshot:
    total_suppliers: int
    active_suppliers: int
    total_annual_spend: float
    strategic_suppliers: int
    preferred_suppliers: int
    restricted_suppliers: int
    blocked_suppliers: int
    country_concentration: dict[str, float]
    category_concentration: dict[str, float]
    single_source_categories: tuple[str, ...]
    records: tuple[SupplierPortfolioRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class SupplierPortfolioService:
    """Classify suppliers and identify portfolio concentration risk."""

    def build(
        self,
        suppliers: Iterable[SupplierPortfolioInput],
    ) -> SupplierPortfolioSnapshot:
        items = list(suppliers)
        total_spend = sum(max(0.0, item.annual_spend) for item in items)

        country_spend: dict[str, float] = {}
        category_spend: dict[str, float] = {}
        category_supplier_ids: dict[str, set[str]] = {}

        for item in items:
            spend = max(0.0, item.annual_spend)
            country_spend[item.country] = country_spend.get(item.country, 0.0) + spend
            category_spend[item.category] = (
                category_spend.get(item.category, 0.0) + spend
            )
            if item.active and item.approved:
                category_supplier_ids.setdefault(item.category, set()).add(
                    item.supplier_id
                )

        records = tuple(
            self._classify(item, total_spend)
            for item in items
        )

        single_source_categories = tuple(
            sorted(
                category
                for category, supplier_ids in category_supplier_ids.items()
                if len(supplier_ids) == 1
            )
        )

        return SupplierPortfolioSnapshot(
            total_suppliers=len(items),
            active_suppliers=sum(1 for item in items if item.active),
            total_annual_spend=round(total_spend, 2),
            strategic_suppliers=sum(
                1
                for item in records
                if item.tier == SupplierPortfolioTier.STRATEGIC
            ),
            preferred_suppliers=sum(
                1
                for item in records
                if item.tier == SupplierPortfolioTier.PREFERRED
            ),
            restricted_suppliers=sum(
                1
                for item in records
                if item.tier == SupplierPortfolioTier.RESTRICTED
            ),
            blocked_suppliers=sum(
                1
                for item in records
                if item.tier == SupplierPortfolioTier.BLOCKED
            ),
            country_concentration=self._percentages(
                country_spend,
                total_spend,
            ),
            category_concentration=self._percentages(
                category_spend,
                total_spend,
            ),
            single_source_categories=single_source_categories,
            records=tuple(
                sorted(
                    records,
                    key=lambda item: (
                        -item.concentration_percent,
                        -item.composite_score,
                        item.supplier_name,
                    ),
                )
            ),
        )

    def _classify(
        self,
        item: SupplierPortfolioInput,
        total_spend: float,
    ) -> SupplierPortfolioRecord:
        warnings: list[str] = []

        score = round(
            item.quality_score * 0.22
            + item.delivery_score * 0.20
            + item.price_score * 0.14
            + item.responsiveness_score * 0.10
            + item.compliance_score * 0.20
            + item.capacity_score * 0.14
        )
        score = max(0, min(100, score))

        if not item.sanctions_clear:
            tier = SupplierPortfolioTier.BLOCKED
            warnings.append("Supplier has not passed sanctions screening.")
        elif not item.active or not item.approved:
            tier = SupplierPortfolioTier.RESTRICTED
            warnings.append("Supplier is inactive or not approved.")
        elif not item.documents_complete or item.compliance_score < 60:
            tier = SupplierPortfolioTier.CONDITIONAL
            warnings.append("Supplier documentation or compliance is incomplete.")
        elif score >= 90 and item.dispute_count == 0:
            tier = SupplierPortfolioTier.STRATEGIC
        elif score >= 80:
            tier = SupplierPortfolioTier.PREFERRED
        elif score >= 65:
            tier = SupplierPortfolioTier.APPROVED
        elif score >= 45:
            tier = SupplierPortfolioTier.CONDITIONAL
        else:
            tier = SupplierPortfolioTier.RESTRICTED

        concentration = (
            max(0.0, item.annual_spend) / total_spend * 100.0
            if total_spend > 0
            else 0.0
        )

        if concentration >= 35:
            warnings.append("Supplier concentration exceeds 35 percent.")
        if item.backup_supplier_count == 0:
            warnings.append("No approved backup supplier is recorded.")
        if item.dispute_count > 0:
            warnings.append("Supplier has recorded commercial disputes.")

        recommended_action = (
            "Block commercial execution and escalate compliance review."
            if tier == SupplierPortfolioTier.BLOCKED
            else "Develop an approved backup supplier."
            if item.backup_supplier_count == 0
            else "Reduce supplier concentration."
            if concentration >= 35
            else "Complete remediation and requalification."
            if tier in {
                SupplierPortfolioTier.CONDITIONAL,
                SupplierPortfolioTier.RESTRICTED,
            }
            else "Maintain and monitor supplier relationship."
        )

        return SupplierPortfolioRecord(
            supplier_id=item.supplier_id,
            supplier_name=item.supplier_name,
            country=item.country,
            category=item.category,
            tier=tier,
            composite_score=score,
            annual_spend=round(max(0.0, item.annual_spend), 2),
            concentration_percent=round(concentration, 2),
            backup_coverage=item.backup_supplier_count > 0,
            warnings=tuple(warnings),
            recommended_action=recommended_action,
        )

    @staticmethod
    def _percentages(
        values: dict[str, float],
        total: float,
    ) -> dict[str, float]:
        if total <= 0:
            return {key: 0.0 for key in values}
        return {
            key: round(value / total * 100.0, 2)
            for key, value in sorted(values.items())
        }


_service = SupplierPortfolioService()


def get_supplier_portfolio_service() -> SupplierPortfolioService:
    return _service