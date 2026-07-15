from dataclasses import dataclass
from typing import Optional


@dataclass
class LandedCost:
    name: str
    rfq_id: Optional[int]
    supplier_quote_id: Optional[int]
    product_name: str
    supplier_name: Optional[str]
    origin_country: Optional[str]
    destination: str

    source_currency: str
    reporting_currency: str
    exchange_rate: float

    quantity: float
    unit: str
    unit_price_source: float

    goods_value_source: float
    goods_value_reporting: float

    international_freight: float = 0.0
    international_insurance: float = 0.0
    origin_charges: float = 0.0
    destination_port_charges: float = 0.0
    customs_broker_fee: float = 0.0
    biosecurity_fee: float = 0.0
    inspection_fee: float = 0.0
    duty_rate: float = 0.0
    duty_amount: float = 0.0
    gst_rate: float = 10.0
    gst_amount: float = 0.0
    local_transport: float = 0.0
    warehouse_cost: float = 0.0
    packaging_cost: float = 0.0
    bank_fee: float = 0.0
    finance_cost: float = 0.0
    contingency: float = 0.0
    other_costs: float = 0.0

    total_landed_cost: float = 0.0
    landed_cost_per_unit: float = 0.0

    selling_price_per_unit: float = 0.0
    expected_revenue: float = 0.0
    gross_profit: float = 0.0
    gross_margin_percent: float = 0.0
    roi_percent: float = 0.0

    status: str = "Draft"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None