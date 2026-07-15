from dataclasses import dataclass
from typing import Optional


@dataclass
class RFQ:
    rfq_number: str
    title: str
    product_id: Optional[int]
    product_name: str
    opportunity_id: Optional[int]
    supplier_id: Optional[int]
    supplier_name: Optional[str]
    quantity: str
    unit: str
    specifications: Optional[str] = None
    packaging_requirements: Optional[str] = None
    certificate_requirements: Optional[str] = None
    destination: Optional[str] = None
    preferred_incoterm: Optional[str] = None
    sample_requirements: Optional[str] = None
    payment_requirements: Optional[str] = None
    required_documents: Optional[str] = None
    response_deadline: Optional[str] = None
    status: str = "Draft"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None