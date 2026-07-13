from dataclasses import dataclass
from typing import Optional


@dataclass
class Supplier:
    company_name: str
    category: str
    country: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None
