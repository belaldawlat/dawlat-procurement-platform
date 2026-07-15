from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.inventory_item import (
    InventoryItem,
    InventoryMovement,
)


INBOUND_MOVEMENTS = {
    "Opening Balance",
    "Purchase Receipt",
    "Customer Return",
    "Warehouse Transfer In",
    "Stock Adjustment Increase",
}

OUTBOUND_MOVEMENTS = {
    "Sales Dispatch",
    "Supplier Return",
    "Warehouse Transfer Out",
    "Stock Adjustment Decrease",
    "Write-Off",
    "Sample Issued",
}

RESERVATION_INCREASE_MOVEMENTS = {
    "Reserve Stock",
}

RESERVATION_DECREASE_MOVEMENTS = {
    "Release Reservation",
}

DAMAGE_INCREASE_MOVEMENTS = {
    "Mark Damaged",
}

DAMAGE_DECREASE_MOVEMENTS = {
    "Restore Damaged Stock",
}


def ensure_inventory_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                product_id INTEGER,
                product_name TEXT NOT NULL,
                sku TEXT NOT NULL,

                warehouse_quote_id INTEGER,
                warehouse_name TEXT NOT NULL,
                warehouse_location TEXT,

                batch_number TEXT,
                lot_number TEXT,
                serial_number TEXT,

                received_date TEXT,
                manufacture_date TEXT,
                expiry_date TEXT,

                unit TEXT NOT NULL,

                quantity_on_hand REAL NOT NULL DEFAULT 0,
                quantity_reserved REAL NOT NULL DEFAULT 0,
                quantity_damaged REAL NOT NULL DEFAULT 0,

                reorder_level REAL NOT NULL DEFAULT 0,
                maximum_stock_level REAL NOT NULL DEFAULT 0,

                unit_cost REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'AUD',

                storage_location TEXT,
                country_of_origin TEXT,
                supplier_name TEXT,

                status TEXT NOT NULL DEFAULT 'Active',
                notes TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (product_id)
                    REFERENCES products (id),

                FOREIGN KEY (warehouse_quote_id)
                    REFERENCES warehouse_quotes (id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                inventory_item_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                movement_date TEXT NOT NULL,

                reference_type TEXT,
                reference_number TEXT,

                from_location TEXT,
                to_location TEXT,

                reason TEXT,
                notes TEXT,

                created_at TEXT NOT NULL,

                FOREIGN KEY (inventory_item_id)
                    REFERENCES inventory_items (id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_inventory_items_product
            ON inventory_items (product_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_inventory_items_sku
            ON inventory_items (sku)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_inventory_movements_item
            ON inventory_movements (inventory_item_id)
            """
        )

        connection.commit()


def row_to_inventory_item(row) -> InventoryItem:
    return InventoryItem(
        id=row["id"],
        product_id=row["product_id"],
        product_name=row["product_name"],
        sku=row["sku"],
        warehouse_quote_id=row["warehouse_quote_id"],
        warehouse_name=row["warehouse_name"],
        warehouse_location=row["warehouse_location"],
        batch_number=row["batch_number"],
        lot_number=row["lot_number"],
        serial_number=row["serial_number"],
        received_date=row["received_date"],
        manufacture_date=row["manufacture_date"],
        expiry_date=row["expiry_date"],
        unit=row["unit"],
        quantity_on_hand=float(row["quantity_on_hand"]),
        quantity_reserved=float(row["quantity_reserved"]),
        quantity_damaged=float(row["quantity_damaged"]),
        reorder_level=float(row["reorder_level"]),
        maximum_stock_level=float(
            row["maximum_stock_level"]
        ),
        unit_cost=float(row["unit_cost"]),
        currency=row["currency"],
        storage_location=row["storage_location"],
        country_of_origin=row["country_of_origin"],
        supplier_name=row["supplier_name"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_inventory_movement(row) -> InventoryMovement:
    return InventoryMovement(
        id=row["id"],
        inventory_item_id=row["inventory_item_id"],
        movement_type=row["movement_type"],
        quantity=float(row["quantity"]),
        movement_date=row["movement_date"],
        reference_type=row["reference_type"],
        reference_number=row["reference_number"],
        from_location=row["from_location"],
        to_location=row["to_location"],
        reason=row["reason"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def create_inventory_item(
    item: InventoryItem,
) -> int:
    ensure_inventory_tables()

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO inventory_items (
                product_id,
                product_name,
                sku,

                warehouse_quote_id,
                warehouse_name,
                warehouse_location,

                batch_number,
                lot_number,
                serial_number,

                received_date,
                manufacture_date,
                expiry_date,

                unit,

                quantity_on_hand,
                quantity_reserved,
                quantity_damaged,

                reorder_level,
                maximum_stock_level,

                unit_cost,
                currency,

                storage_location,
                country_of_origin,
                supplier_name,

                status,
                notes,

                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                item.product_id,
                item.product_name.strip(),
                item.sku.strip(),

                item.warehouse_quote_id,
                item.warehouse_name.strip(),
                (
                    item.warehouse_location.strip()
                    if item.warehouse_location
                    else None
                ),

                (
                    item.batch_number.strip()
                    if item.batch_number
                    else None
                ),
                (
                    item.lot_number.strip()
                    if item.lot_number
                    else None
                ),
                (
                    item.serial_number.strip()
                    if item.serial_number
                    else None
                ),

                item.received_date,
                item.manufacture_date,
                item.expiry_date,

                item.unit.strip(),

                item.quantity_on_hand,
                item.quantity_reserved,
                item.quantity_damaged,

                item.reorder_level,
                item.maximum_stock_level,

                item.unit_cost,
                item.currency,

                (
                    item.storage_location.strip()
                    if item.storage_location
                    else None
                ),
                (
                    item.country_of_origin.strip()
                    if item.country_of_origin
                    else None
                ),
                (
                    item.supplier_name.strip()
                    if item.supplier_name
                    else None
                ),

                item.status,
                (
                    item.notes.strip()
                    if item.notes
                    else None
                ),

                timestamp,
                timestamp,
            ),
        )

        item_id = int(cursor.lastrowid)

        if item.quantity_on_hand > 0:
            connection.execute(
                """
                INSERT INTO inventory_movements (
                    inventory_item_id,
                    movement_type,
                    quantity,
                    movement_date,
                    reference_type,
                    reference_number,
                    from_location,
                    to_location,
                    reason,
                    notes,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    "Opening Balance",
                    item.quantity_on_hand,
                    (
                        item.received_date
                        or datetime.now().date().isoformat()
                    ),
                    "Inventory Setup",
                    None,
                    None,
                    item.warehouse_name,
                    "Initial stock balance",
                    item.notes,
                    timestamp,
                ),
            )

        connection.commit()

    return item_id


def get_inventory_items(
    search: str = "",
    status: str = "All",
    warehouse_name: str = "All",
    stock_filter: str = "All",
) -> list[InventoryItem]:
    ensure_inventory_tables()

    query = """
        SELECT *
        FROM inventory_items
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                product_name LIKE ?
                OR sku LIKE ?
                OR warehouse_name LIKE ?
                OR warehouse_location LIKE ?
                OR batch_number LIKE ?
                OR lot_number LIKE ?
                OR serial_number LIKE ?
                OR supplier_name LIKE ?
                OR country_of_origin LIKE ?
            )
        """

        parameters.extend([search_value] * 9)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    if warehouse_name != "All":
        query += " AND warehouse_name = ?"
        parameters.append(warehouse_name)

    if stock_filter == "Reorder Required":
        query += """
            AND (
                quantity_on_hand
                - quantity_reserved
                - quantity_damaged
            ) <= reorder_level
        """

    elif stock_filter == "Out of Stock":
        query += """
            AND (
                quantity_on_hand
                - quantity_reserved
                - quantity_damaged
            ) <= 0
        """

    elif stock_filter == "Available Stock":
        query += """
            AND (
                quantity_on_hand
                - quantity_reserved
                - quantity_damaged
            ) > 0
        """

    elif stock_filter == "Damaged Stock":
        query += " AND quantity_damaged > 0"

    query += """
        ORDER BY
            CASE
                WHEN (
                    quantity_on_hand
                    - quantity_reserved
                    - quantity_damaged
                ) <= reorder_level
                THEN 0
                ELSE 1
            END,
            product_name ASC,
            id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [
        row_to_inventory_item(row)
        for row in rows
    ]


def get_inventory_item_by_id(
    item_id: int,
) -> Optional[InventoryItem]:
    ensure_inventory_tables()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM inventory_items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

    return (
        row_to_inventory_item(row)
        if row
        else None
    )


def get_inventory_warehouse_names() -> list[str]:
    ensure_inventory_tables()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT warehouse_name
            FROM inventory_items
            WHERE warehouse_name IS NOT NULL
              AND warehouse_name != ''
            ORDER BY warehouse_name ASC
            """
        ).fetchall()

    return [
        row["warehouse_name"]
        for row in rows
    ]


def create_inventory_movement(
    movement: InventoryMovement,
) -> int:
    ensure_inventory_tables()

    if movement.quantity <= 0:
        raise ValueError(
            "Movement quantity must be greater than zero."
        )

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM inventory_items
            WHERE id = ?
            """,
            (movement.inventory_item_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                "Inventory item was not found."
            )

        quantity_on_hand = float(
            row["quantity_on_hand"]
        )

        quantity_reserved = float(
            row["quantity_reserved"]
        )

        quantity_damaged = float(
            row["quantity_damaged"]
        )

        movement_type = movement.movement_type
        quantity = movement.quantity

        if movement_type in INBOUND_MOVEMENTS:
            quantity_on_hand += quantity

        elif movement_type in OUTBOUND_MOVEMENTS:
            available_quantity = (
                quantity_on_hand
                - quantity_reserved
                - quantity_damaged
            )

            if quantity > available_quantity:
                raise ValueError(
                    "The movement exceeds available stock."
                )

            quantity_on_hand -= quantity

        elif movement_type in (
            RESERVATION_INCREASE_MOVEMENTS
        ):
            available_quantity = (
                quantity_on_hand
                - quantity_reserved
                - quantity_damaged
            )

            if quantity > available_quantity:
                raise ValueError(
                    "The reservation exceeds available stock."
                )

            quantity_reserved += quantity

        elif movement_type in (
            RESERVATION_DECREASE_MOVEMENTS
        ):
            if quantity > quantity_reserved:
                raise ValueError(
                    "The release exceeds reserved stock."
                )

            quantity_reserved -= quantity

        elif movement_type in (
            DAMAGE_INCREASE_MOVEMENTS
        ):
            available_quantity = (
                quantity_on_hand
                - quantity_reserved
                - quantity_damaged
            )

            if quantity > available_quantity:
                raise ValueError(
                    "The damaged quantity exceeds available stock."
                )

            quantity_damaged += quantity

        elif movement_type in (
            DAMAGE_DECREASE_MOVEMENTS
        ):
            if quantity > quantity_damaged:
                raise ValueError(
                    "The restored quantity exceeds damaged stock."
                )

            quantity_damaged -= quantity

        else:
            raise ValueError(
                "Unsupported inventory movement type."
            )

        cursor = connection.execute(
            """
            INSERT INTO inventory_movements (
                inventory_item_id,
                movement_type,
                quantity,
                movement_date,
                reference_type,
                reference_number,
                from_location,
                to_location,
                reason,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                movement.inventory_item_id,
                movement.movement_type,
                movement.quantity,
                movement.movement_date,
                movement.reference_type,
                movement.reference_number,
                movement.from_location,
                movement.to_location,
                movement.reason,
                movement.notes,
                timestamp,
            ),
        )

        connection.execute(
            """
            UPDATE inventory_items
            SET quantity_on_hand = ?,
                quantity_reserved = ?,
                quantity_damaged = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                quantity_on_hand,
                quantity_reserved,
                quantity_damaged,
                timestamp,
                movement.inventory_item_id,
            ),
        )

        connection.commit()

    return int(cursor.lastrowid)


def get_inventory_movements(
    inventory_item_id: Optional[int] = None,
    search: str = "",
    movement_type: str = "All",
) -> list[InventoryMovement]:
    ensure_inventory_tables()

    query = """
        SELECT *
        FROM inventory_movements
        WHERE 1 = 1
    """

    parameters: list = []

    if inventory_item_id is not None:
        query += " AND inventory_item_id = ?"
        parameters.append(inventory_item_id)

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                reference_type LIKE ?
                OR reference_number LIKE ?
                OR from_location LIKE ?
                OR to_location LIKE ?
                OR reason LIKE ?
                OR notes LIKE ?
            )
        """

        parameters.extend([search_value] * 6)

    if movement_type != "All":
        query += " AND movement_type = ?"
        parameters.append(movement_type)

    query += """
        ORDER BY movement_date DESC, id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [
        row_to_inventory_movement(row)
        for row in rows
    ]


def update_inventory_settings(
    item_id: int,
    *,
    reorder_level: float,
    maximum_stock_level: float,
    unit_cost: float,
    status: str,
    storage_location: str,
    notes: str,
) -> None:
    ensure_inventory_tables()

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE inventory_items
            SET reorder_level = ?,
                maximum_stock_level = ?,
                unit_cost = ?,
                status = ?,
                storage_location = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                reorder_level,
                maximum_stock_level,
                unit_cost,
                status,
                (
                    storage_location.strip()
                    if storage_location
                    else None
                ),
                notes.strip() if notes else None,
                timestamp,
                item_id,
            ),
        )

        connection.commit()


def delete_inventory_item(
    item_id: int,
) -> None:
    ensure_inventory_tables()

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM inventory_movements
            WHERE inventory_item_id = ?
            """,
            (item_id,),
        )

        connection.execute(
            """
            DELETE FROM inventory_items
            WHERE id = ?
            """,
            (item_id,),
        )

        connection.commit()