from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Shipment:
    shipment_number: str
    shipment_type: str
    status: str

    rfq_id: Optional[int]
    supplier_quote_id: Optional[int]
    logistics_quote_id: Optional[int]
    warehouse_quote_id: Optional[int]

    supplier_name: str
    logistics_provider: Optional[str]
    warehouse_name: Optional[str]

    product_name: str
    cargo_description: str
    quantity: float
    unit: str
    gross_weight_kg: float
    volume_cbm: float

    origin_country: str
    origin_location: str
    destination_country: str
    destination_location: str

    transport_mode: str
    service_type: str
    incoterm: str
    container_type: Optional[str]

    booking_number: Optional[str]
    bill_of_lading_number: Optional[str]
    airway_bill_number: Optional[str]
    container_number: Optional[str]
    seal_number: Optional[str]
    tracking_number: Optional[str]

    carrier_name: Optional[str]
    vessel_name: Optional[str]
    voyage_number: Optional[str]
    flight_number: Optional[str]

    planned_pickup_date: Optional[str]
    actual_pickup_date: Optional[str]
    etd: Optional[str]
    actual_departure_date: Optional[str]
    eta: Optional[str]
    actual_arrival_date: Optional[str]
    customs_clearance_date: Optional[str]
    warehouse_delivery_date: Optional[str]

    customs_status: str
    biosecurity_status: str
    inspection_status: str
    document_status: str

    commercial_invoice_received: bool
    packing_list_received: bool
    bill_of_lading_received: bool
    certificate_of_origin_received: bool
    phytosanitary_received: bool
    fumigation_received: bool
    insurance_certificate_received: bool
    import_permit_received: bool
    other_documents: Optional[str]

    currency: str
    goods_value: float
    freight_cost: float
    insurance_cost: float
    customs_cost: float
    biosecurity_cost: float
    port_cost: float
    local_delivery_cost: float
    storage_cost: float
    other_costs: float

    delay_reason: Optional[str]
    risk_level: str
    priority: str

    inventory_received: bool = False
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None

    @property
    def total_shipment_cost(self) -> float:
        return (
            self.freight_cost
            + self.insurance_cost
            + self.customs_cost
            + self.biosecurity_cost
            + self.port_cost
            + self.local_delivery_cost
            + self.storage_cost
            + self.other_costs
        )

    @property
    def total_value(self) -> float:
        return self.goods_value + self.total_shipment_cost

    @property
    def document_completion_percent(self) -> int:
        documents = [
            self.commercial_invoice_received,
            self.packing_list_received,
            self.bill_of_lading_received,
            self.certificate_of_origin_received,
            self.phytosanitary_received,
            self.fumigation_received,
            self.insurance_certificate_received,
            self.import_permit_received,
        ]

        completed = sum(1 for document in documents if document)

        return round((completed / len(documents)) * 100)

    @property
    def is_overdue(self) -> bool:
        if not self.eta:
            return False

        if self.status in {
            "Delivered",
            "Completed",
            "Cancelled",
        }:
            return False

        try:
            eta_date = date.fromisoformat(self.eta)
        except ValueError:
            return False

        return eta_date < date.today()


@dataclass
class ShipmentMilestone:
    shipment_id: int
    milestone_type: str
    milestone_date: str
    status: str

    location: Optional[str] = None
    description: Optional[str] = None
    responsible_party: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

    created_at: Optional[str] = None
    id: Optional[int] = None