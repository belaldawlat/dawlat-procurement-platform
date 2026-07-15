from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    company_name: str
    customer_type: str
    country: str
    city: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    products_of_interest: Optional[str] = None
    estimated_demand: Optional[str] = None
    preferred_packaging: Optional[str] = None
    payment_terms: Optional[str] = None
    credit_status: str = "Not Assessed"
    lead_status: str = "Prospect"
    source: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None