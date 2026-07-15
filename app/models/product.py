from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    name: str
    category: str
    sku: str
    unit: str
    country_of_origin: Optional[str] = None
    description: Optional[str] = None
    specifications: Optional[str] = None
    packaging: Optional[str] = None
    required_certificates: Optional[str] = None
    storage_requirements: Optional[str] = None
    status: str = "Active"
    id: Optional[int] = None