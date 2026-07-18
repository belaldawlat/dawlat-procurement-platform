"""Financial exposure intelligence for executive dashboards."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable

class ExposureLevel(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"

@dataclass(frozen=True)
class FinancialExposureItem:
    case_id: str
    cleared_buyer_funds: float
    supplier_obligation: float
    protected_profit: float
    expected_landed_cost: float
    expected_revenue: float
    fx_exposure: float
    receivable_amount: float
    overdue_receivable_amount: float
    authorised_exposure_limit: float

@dataclass(frozen=True)
class FinancialExposureSnapshot:
    total_cleared_buyer_funds: float
    total_supplier_obligations: float
    protected_profit: float
    committed_cash: float
    unprotected_exposure: float
    fx_exposure: float
    expected_landed_cost: float
    expected_revenue: float
    margin_leakage: float
    overdue_receivables: float
    exposure_utilisation_percent: float
    exposure_level: ExposureLevel
    blocked_case_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class FinancialExposureService:
    def calculate(
        self,
        items: Iterable[FinancialExposureItem],
    ) -> FinancialExposureSnapshot:
        records = list(items)
        warnings: list[str] = []
        blocked: list[str] = []

        funds = sum(item.cleared_buyer_funds for item in records)
        obligations = sum(item.supplier_obligation for item in records)
        protected_profit = sum(item.protected_profit for item in records)
        landed_cost = sum(item.expected_landed_cost for item in records)
        revenue = sum(item.expected_revenue for item in records)
        fx_exposure = sum(abs(item.fx_exposure) for item in records)
        overdue = sum(item.overdue_receivable_amount for item in records)
        authorised_limit = sum(
            max(0.0, item.authorised_exposure_limit)
            for item in records
        )

        unprotected = max(0.0, obligations - funds)
        expected_profit = max(0.0, revenue - landed_cost)
        margin_leakage = max(0.0, protected_profit - expected_profit)
        utilisation = (
            obligations / authorised_limit * 100.0
            if authorised_limit > 0
            else 100.0 if obligations > 0 else 0.0
        )

        for item in records:
            if item.supplier_obligation > item.cleared_buyer_funds:
                blocked.append(item.case_id)

        if unprotected > 0:
            warnings.append("Supplier obligations exceed cleared buyer funds.")
        if overdue > 0:
            warnings.append("Overdue receivables require collection action.")
        if margin_leakage > 0:
            warnings.append("Expected profit is below the protected profit target.")

        if utilisation >= 100:
            level = ExposureLevel.CRITICAL
        elif utilisation >= 80:
            level = ExposureLevel.HIGH
        elif utilisation >= 50:
            level = ExposureLevel.MODERATE
        else:
            level = ExposureLevel.LOW

        return FinancialExposureSnapshot(
            total_cleared_buyer_funds=round(funds, 2),
            total_supplier_obligations=round(obligations, 2),
            protected_profit=round(protected_profit, 2),
            committed_cash=round(min(funds, obligations), 2),
            unprotected_exposure=round(unprotected, 2),
            fx_exposure=round(fx_exposure, 2),
            expected_landed_cost=round(landed_cost, 2),
            expected_revenue=round(revenue, 2),
            margin_leakage=round(margin_leakage, 2),
            overdue_receivables=round(overdue, 2),
            exposure_utilisation_percent=round(utilisation, 2),
            exposure_level=level,
            blocked_case_ids=tuple(dict.fromkeys(blocked)),
            warnings=tuple(warnings),
        )

_service = FinancialExposureService()

def get_financial_exposure_service() -> FinancialExposureService:
    return _service