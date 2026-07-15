from dataclasses import dataclass
from typing import Optional


@dataclass
class WarehouseQuote:
    provider_name: str
    provider_type: str

    logistics_quote_id: Optional[int]
    rfq_id: Optional[int]
    supplier_quote_id: Optional[int]

    country: str
    state_region: Optional[str]
    city: str
    address: Optional[str]

    warehouse_type: str
    service_model: str
    temperature_controlled: bool
    bonded_warehouse: bool
    food_grade: bool

    product_description: str
    quantity: float
    storage_unit: str
    estimated_storage_days: int

    currency: str

    receiving_fee: float
    container_unloading_fee: float
    devanning_fee: float
    storage_rate: float
    minimum_monthly_charge: float
    pallet_in_fee: float
    pallet_out_fee: float
    pick_pack_fee: float
    labelling_fee: float
    repacking_fee: float
    cross_docking_fee: float
    inventory_management_fee: float
    local_delivery_fee: float
    disposal_fee: float
    other_costs: float

    free_storage_days: int
    minimum_term_months: int

    capacity_description: Optional[str]
    delivery_zones: Optional[str]
    operating_hours: Optional[str]
    systems_integrations: Optional[str]
    insurance_details: Optional[str]
    certifications: Optional[str]
    inclusions: Optional[str]
    exclusions: Optional[str]

    price_score: int
    location_score: int
    service_score: int
    capacity_score: int
    technology_score: int
    reliability_score: int
    communication_score: int
    compliance_score: int
    risk_score: int

    status: str = "Received"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None

    @property
    def estimated_storage_cost(self) -> float:
        chargeable_days = max(
            0,
            self.estimated_storage_days - self.free_storage_days,
        )

        return self.storage_rate * chargeable_days * self.quantity

    @property
    def total_estimated_cost(self) -> float:
        calculated_total = (
            self.receiving_fee
            + self.container_unloading_fee
            + self.devanning_fee
            + self.estimated_storage_cost
            + self.pallet_in_fee
            + self.pallet_out_fee
            + self.pick_pack_fee
            + self.labelling_fee
            + self.repacking_fee
            + self.cross_docking_fee
            + self.inventory_management_fee
            + self.local_delivery_fee
            + self.disposal_fee
            + self.other_costs
        )

        return max(
            calculated_total,
            self.minimum_monthly_charge,
        )