from dataclasses import dataclass
from typing import Optional


@dataclass
class Partner:
    company_name: str
    partner_type: str
    country: str
    city: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    products_services: Optional[str] = None
    status: str = "Prospect"
    verification_status: str = "Unverified"
    rating: int = 0
    notes: Optional[str] = None
    id: Optional[int] = None