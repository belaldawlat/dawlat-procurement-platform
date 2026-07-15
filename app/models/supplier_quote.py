from dataclasses import dataclass
from typing import Optional


@dataclass
class SupplierQuote:
    rfq_id: int
    supplier_id: Optional[int]
    supplier_name: str
    quote_reference: Optional[str]
    currency: str
    unit_price: float
    quantity: float
    freight_cost: float = 0.0
    insurance_cost: float = 0.0
    other_costs: float = 0.0
    incoterm: str = "CIF"
    moq: Optional[str] = None
    lead_time_days: int = 0
    payment_terms: Optional[str] = None
    packaging: Optional[str] = None
    certificates: Optional[str] = None
    sample_available: bool = False
    sample_cost: float = 0.0
    quotation_valid_until: Optional[str] = None
    quality_score: int = 50
    compliance_score: int = 50
    communication_score: int = 50
    reliability_score: int = 50
    risk_score: int = 50
    status: str = "Received"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None

    @property
    def goods_total(self) -> float:
        return self.unit_price * self.quantity

    @property
    def quoted_total(self) -> float:
        return (
            self.goods_total
            + self.freight_cost
            + self.insurance_cost
            + self.other_costs
        )