from dataclasses import dataclass
from typing import Optional


@dataclass
class InventoryItem:
    product_id: Optional[int]
    product_name: str
    sku: str

    warehouse_quote_id: Optional[int]
    warehouse_name: str
    warehouse_location: Optional[str]

    batch_number: Optional[str]
    lot_number: Optional[str]
    serial_number: Optional[str]

    received_date: Optional[str]
    manufacture_date: Optional[str]
    expiry_date: Optional[str]

    unit: str
    quantity_on_hand: float
    quantity_reserved: float
    quantity_damaged: float
    reorder_level: float
    maximum_stock_level: float

    unit_cost: float
    currency: str

    storage_location: Optional[str]
    country_of_origin: Optional[str]
    supplier_name: Optional[str]

    status: str = "Active"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None

    @property
    def available_quantity(self) -> float:
        return max(
            0,
            self.quantity_on_hand
            - self.quantity_reserved
            - self.quantity_damaged,
        )

    @property
    def stock_value(self) -> float:
        return self.quantity_on_hand * self.unit_cost

    @property
    def available_stock_value(self) -> float:
        return self.available_quantity * self.unit_cost

    @property
    def needs_reordering(self) -> bool:
        return self.available_quantity <= self.reorder_level


@dataclass
class InventoryMovement:
    inventory_item_id: int
    movement_type: str
    quantity: float
    movement_date: str

    reference_type: Optional[str] = None
    reference_number: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None

    created_at: Optional[str] = None
    id: Optional[int] = None