from dataclasses import dataclass
from typing import Optional


@dataclass
class LogisticsQuote:
    provider_name: str
    provider_type: str
    rfq_id: Optional[int]
    supplier_quote_id: Optional[int]

    origin_country: str
    origin_city_port: Optional[str]
    destination_country: str
    destination_city_port: str

    transport_mode: str
    service_type: str
    container_type: Optional[str]
    incoterm: Optional[str]

    cargo_description: str
    quantity: float
    unit: str
    gross_weight_kg: float
    volume_cbm: float

    currency: str
    freight_cost: float
    origin_charges: float
    destination_charges: float
    customs_clearance_fee: float
    biosecurity_fee: float
    inspection_fee: float
    local_delivery_fee: float
    warehouse_fee: float
    insurance_cost: float
    documentation_fee: float
    other_costs: float

    transit_days: int
    validity_date: Optional[str]
    departure_frequency: Optional[str]
    route_details: Optional[str]
    inclusions: Optional[str]
    exclusions: Optional[str]

    reliability_score: int
    communication_score: int
    price_score: int
    service_score: int
    risk_score: int

    status: str = "Received"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None

    @property
    def total_cost(self) -> float:
        return (
            self.freight_cost
            + self.origin_charges
            + self.destination_charges
            + self.customs_clearance_fee
            + self.biosecurity_fee
            + self.inspection_fee
            + self.local_delivery_fee
            + self.warehouse_fee
            + self.insurance_cost
            + self.documentation_fee
            + self.other_costs
        )