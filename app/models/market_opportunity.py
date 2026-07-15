from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketOpportunity:

    title: str
    product: str
    industry: str
    country: str
    state: Optional[str] = None
    city: Optional[str] = None

    buyer_company: Optional[str] = None

    opportunity_type: str = "Import"

    estimated_quantity: Optional[str] = None

    target_price: Optional[str] = None

    estimated_landed_cost: Optional[str] = None

    estimated_sale_price: Optional[str] = None

    expected_margin: Optional[str] = None

    urgency: str = "Medium"

    demand_score: int = 50

    competition_score: int = 50

    confidence_score: int = 50

    status: str = "Research"

    source: Optional[str] = None

    notes: Optional[str] = None

    id: Optional[int] = None