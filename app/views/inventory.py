from datetime import date

import streamlit as st

from models.inventory_item import (
    InventoryItem,
    InventoryMovement,
)
from services.inventory_service import (
    create_inventory_item,
    create_inventory_movement,
    delete_inventory_item,
    ensure_inventory_tables,
    get_inventory_items,
    get_inventory_movements,
    get_inventory_warehouse_names,
    update_inventory_settings,
)
from services.product_service import get_products
from services.warehouse_quote_service import (
    get_warehouse_quotes,
)


CURRENCIES = [
    "AUD",
    "USD",
    "EUR",
    "GBP",
    "CNY",
    "VND",
    "PKR",
    "INR",
]

ITEM_STATUSES = [
    "Active",
    "Quarantined",
    "Quality Hold",
    "Blocked",
    "Discontinued",
    "Expired",
]

MOVEMENT_TYPES = [
    "Purchase Receipt",
    "Sales Dispatch",
    "Customer Return",
    "Supplier Return",
    "Warehouse Transfer In",
    "Warehouse Transfer Out",
    "Reserve Stock",
    "Release Reservation",
    "Mark Damaged",
    "Restore Damaged Stock",
    "Sample Issued",
    "Write-Off",
    "Stock Adjustment Increase",
    "Stock Adjustment Decrease",
]


def show() -> None:
    ensure_inventory_tables()

    st.title("📦 Inventory Management")
    st.caption(
        "Manage products, warehouse stock, batches, lots, "
        "expiry dates, reservations, damaged stock, reorder "
        "levels, stock movements and inventory valuation."
    )

    overview_tab, add_tab, movement_tab, register_tab = (
        st.tabs(
            [
                "📊 Inventory Overview",
                "➕ Add Inventory Item",
                "🔄 Stock Movement",
                "📋 Inventory Register",
            ]
        )
    )

    with overview_tab:
        show_overview()

    with add_tab:
        show_add_item()

    with movement_tab:
        show_stock_movement()

    with register_tab:
        show_register()


def show_overview() -> None:
    items = get_inventory_items()

    if not items:
        st.info(
            "No inventory items exist yet. "
            "Add the first inventory item."
        )
        return

    total_items = len(items)

    total_on_hand = sum(
        item.quantity_on_hand
        for item in items
    )

    total_available = sum(
        item.available_quantity
        for item in items
    )

    total_reserved = sum(
        item.quantity_reserved
        for item in items
    )

    total_damaged = sum(
        item.quantity_damaged
        for item in items
    )

    total_value = sum(
        item.stock_value
        for item in items
    )

    reorder_count = sum(
        1
        for item in items
        if item.needs_reordering
    )

    st.subheader("Executive Stock Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Inventory Records",
        total_items,
    )

    col2.metric(
        "Quantity On Hand",
        f"{total_on_hand:,.2f}",
    )

    col3.metric(
        "Available Quantity",
        f"{total_available:,.2f}",
    )

    col4.metric(
        "Inventory Value",
        f"AUD {total_value:,.2f}",
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Reserved Stock",
        f"{total_reserved:,.2f}",
    )

    col2.metric(
        "Damaged Stock",
        f"{total_damaged:,.2f}",
    )

    col3.metric(
        "Reorder Alerts",
        reorder_count,
    )

    if reorder_count:
        st.warning(
            f"{reorder_count} inventory item(s) require "
            "reordering or management attention."
        )

    st.markdown("---")
    st.subheader("Stock Alerts")

    alert_rows = []

    today = date.today()

    for item in items:
        alert_type = []

        if item.available_quantity <= 0:
            alert_type.append("Out of stock")

        elif item.needs_reordering:
            alert_type.append("Reorder required")

        if item.quantity_damaged > 0:
            alert_type.append("Damaged stock")

        if item.expiry_date:
            expiry_date = date.fromisoformat(
                item.expiry_date
            )

            days_to_expiry = (
                expiry_date - today
            ).days

            if days_to_expiry < 0:
                alert_type.append("Expired")

            elif days_to_expiry <= 90:
                alert_type.append(
                    f"Expires in {days_to_expiry} days"
                )

        if alert_type:
            alert_rows.append(
                {
                    "Product": item.product_name,
                    "SKU": item.sku,
                    "Warehouse": item.warehouse_name,
                    "Batch": item.batch_number or "",
                    "Available": item.available_quantity,
                    "Reorder Level": item.reorder_level,
                    "Expiry": item.expiry_date or "",
                    "Alert": ", ".join(alert_type),
                }
            )

    if alert_rows:
        st.dataframe(
            alert_rows,
            hide_index=True,
            width="stretch",
        )
    else:
        st.success(
            "No urgent inventory alerts."
        )


def show_add_item() -> None:
    st.subheader("Add Inventory Item")

    products = get_products(status="Active")
    warehouse_quotes = get_warehouse_quotes()

    product_mode = st.radio(
        "Product source",
        [
            "Existing Product",
            "Manual Product",
        ],
        horizontal=True,
    )

    selected_product = None
    manual_product_name = ""
    manual_sku = ""
    manual_unit = "unit"
    manual_origin = ""

    if product_mode == "Existing Product":
        if products:
            selected_product = st.selectbox(
                "Product",
                products,
                format_func=lambda product: (
                    f"{product.name} — {product.sku}"
                ),
            )
        else:
            st.info(
                "No active products exist. "
                "Select Manual Product."
            )

    else:
        col1, col2 = st.columns(2)

        with col1:
            manual_product_name = st.text_input(
                "Product name *"
            )

            manual_sku = st.text_input(
                "SKU *"
            )

        with col2:
            manual_unit = st.text_input(
                "Unit",
                value="unit",
            )

            manual_origin = st.text_input(
                "Country of origin"
            )

    warehouse_mode = st.radio(
        "Warehouse source",
        [
            "Existing Warehouse Quote",
            "Manual Warehouse",
        ],
        horizontal=True,
    )

    selected_warehouse = None
    manual_warehouse_name = ""
    manual_warehouse_location = ""

    if warehouse_mode == "Existing Warehouse Quote":
        if warehouse_quotes:
            selected_warehouse = st.selectbox(
                "Warehouse",
                warehouse_quotes,
                format_func=lambda warehouse: (
                    f"{warehouse.provider_name} — "
                    f"{warehouse.city}, "
                    f"{warehouse.country}"
                ),
            )
        else:
            st.info(
                "No warehouse quotations exist. "
                "Select Manual Warehouse."
            )

    else:
        col1, col2 = st.columns(2)

        with col1:
            manual_warehouse_name = st.text_input(
                "Warehouse name *"
            )

        with col2:
            manual_warehouse_location = st.text_input(
                "Warehouse location"
            )

    st.markdown("### Batch and Traceability")

    col1, col2, col3 = st.columns(3)

    with col1:
        batch_number = st.text_input(
            "Batch number"
        )

    with col2:
        lot_number = st.text_input(
            "Lot number"
        )

    with col3:
        serial_number = st.text_input(
            "Serial number"
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        received_date = st.date_input(
            "Received date",
            value=date.today(),
        )

    with col2:
        manufacture_date_enabled = st.checkbox(
            "Record manufacture date"
        )

        manufacture_date = (
            st.date_input(
                "Manufacture date",
                value=date.today(),
            )
            if manufacture_date_enabled
            else None
        )

    with col3:
        expiry_date_enabled = st.checkbox(
            "Record expiry date"
        )

        expiry_date = (
            st.date_input(
                "Expiry date",
                value=date.today(),
            )
            if expiry_date_enabled
            else None
        )

    st.markdown("### Stock Quantities")

    col1, col2, col3 = st.columns(3)

    with col1:
        quantity_on_hand = st.number_input(
            "Opening quantity on hand",
            min_value=0.0,
            value=0.0,
        )

    with col2:
        quantity_reserved = st.number_input(
            "Opening reserved quantity",
            min_value=0.0,
            value=0.0,
        )

    with col3:
        quantity_damaged = st.number_input(
            "Opening damaged quantity",
            min_value=0.0,
            value=0.0,
        )

    col1, col2 = st.columns(2)

    with col1:
        reorder_level = st.number_input(
            "Reorder level",
            min_value=0.0,
            value=0.0,
        )

    with col2:
        maximum_stock_level = st.number_input(
            "Maximum stock level",
            min_value=0.0,
            value=0.0,
        )

    st.markdown("### Cost and Storage")

    col1, col2 = st.columns(2)

    with col1:
        currency = st.selectbox(
            "Currency",
            CURRENCIES,
        )

        unit_cost = st.number_input(
            "Unit cost",
            min_value=0.0,
            value=0.0,
        )

    with col2:
        supplier_name = st.text_input(
            "Supplier name"
        )

        storage_location = st.text_input(
            "Internal storage location",
            placeholder=(
                "Example: Zone A, Rack 4, Bay 2"
            ),
        )

    status = st.selectbox(
        "Inventory status",
        ITEM_STATUSES,
    )

    notes = st.text_area(
        "Notes"
    )

    if not st.button(
        "Save Inventory Item",
        type="primary",
        width="stretch",
    ):
        return

    if product_mode == "Existing Product":
        if selected_product is None:
            st.warning(
                "Select an existing product."
            )
            return

        product_id = selected_product.id
        product_name = selected_product.name
        sku = selected_product.sku
        unit = selected_product.unit
        country_of_origin = (
            selected_product.country_of_origin
        )

    else:
        product_id = None
        product_name = manual_product_name.strip()
        sku = manual_sku.strip()
        unit = manual_unit.strip()
        country_of_origin = manual_origin.strip()

        if not product_name:
            st.warning("Product name is required.")
            return

        if not sku:
            st.warning("SKU is required.")
            return

    if warehouse_mode == "Existing Warehouse Quote":
        if selected_warehouse is None:
            st.warning(
                "Select an existing warehouse."
            )
            return

        warehouse_quote_id = (
            selected_warehouse.id
        )

        warehouse_name = (
            selected_warehouse.provider_name
        )

        warehouse_location = (
            f"{selected_warehouse.city}, "
            f"{selected_warehouse.state_region or ''}, "
            f"{selected_warehouse.country}"
        ).replace(", ,", ",")

    else:
        warehouse_quote_id = None
        warehouse_name = (
            manual_warehouse_name.strip()
        )

        warehouse_location = (
            manual_warehouse_location.strip()
        )

        if not warehouse_name:
            st.warning(
                "Warehouse name is required."
            )
            return

    if quantity_reserved + quantity_damaged > (
        quantity_on_hand
    ):
        st.warning(
            "Reserved and damaged quantities cannot "
            "exceed quantity on hand."
        )
        return

    item_id = create_inventory_item(
        InventoryItem(
            product_id=product_id,
            product_name=product_name,
            sku=sku,
            warehouse_quote_id=warehouse_quote_id,
            warehouse_name=warehouse_name,
            warehouse_location=warehouse_location,
            batch_number=batch_number,
            lot_number=lot_number,
            serial_number=serial_number,
            received_date=received_date.isoformat(),
            manufacture_date=(
                manufacture_date.isoformat()
                if manufacture_date
                else None
            ),
            expiry_date=(
                expiry_date.isoformat()
                if expiry_date
                else None
            ),
            unit=unit,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            quantity_damaged=quantity_damaged,
            reorder_level=reorder_level,
            maximum_stock_level=(
                maximum_stock_level
            ),
            unit_cost=unit_cost,
            currency=currency,
            storage_location=storage_location,
            country_of_origin=country_of_origin,
            supplier_name=supplier_name,
            status=status,
            notes=notes,
        )
    )

    st.success(
        f"Inventory item saved successfully. ID: {item_id}"
    )


def show_stock_movement() -> None:
    st.subheader("Record Stock Movement")

    items = get_inventory_items(
        status="Active"
    )

    if not items:
        st.info(
            "Add an active inventory item first."
        )
        return

    selected_item = st.selectbox(
        "Inventory item",
        items,
        format_func=lambda item: (
            f"{item.product_name} — "
            f"{item.sku} — "
            f"{item.warehouse_name} — "
            f"Available: {item.available_quantity:g} "
            f"{item.unit}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "On Hand",
        f"{selected_item.quantity_on_hand:g}",
    )

    col2.metric(
        "Available",
        f"{selected_item.available_quantity:g}",
    )

    col3.metric(
        "Reserved",
        f"{selected_item.quantity_reserved:g}",
    )

    col4.metric(
        "Damaged",
        f"{selected_item.quantity_damaged:g}",
    )

    movement_type = st.selectbox(
        "Movement type",
        MOVEMENT_TYPES,
    )

    quantity = st.number_input(
        "Movement quantity",
        min_value=0.0,
        value=0.0,
    )

    movement_date = st.date_input(
        "Movement date",
        value=date.today(),
    )

    col1, col2 = st.columns(2)

    with col1:
        reference_type = st.text_input(
            "Reference type",
            placeholder=(
                "Purchase order, sales order, "
                "shipment, adjustment"
            ),
        )

        reference_number = st.text_input(
            "Reference number"
        )

    with col2:
        from_location = st.text_input(
            "From location"
        )

        to_location = st.text_input(
            "To location"
        )

    reason = st.text_input(
        "Reason"
    )

    notes = st.text_area(
        "Movement notes"
    )

    if not st.button(
        "Post Stock Movement",
        type="primary",
        width="stretch",
    ):
        return

    try:
        movement_id = create_inventory_movement(
            InventoryMovement(
                inventory_item_id=selected_item.id,
                movement_type=movement_type,
                quantity=quantity,
                movement_date=(
                    movement_date.isoformat()
                ),
                reference_type=reference_type,
                reference_number=reference_number,
                from_location=from_location,
                to_location=to_location,
                reason=reason,
                notes=notes,
            )
        )

        st.success(
            f"Stock movement posted successfully. "
            f"Movement ID: {movement_id}"
        )

        st.rerun()

    except ValueError as error:
        st.error(str(error))


def show_register() -> None:
    st.subheader("Inventory Register")

    search = st.text_input(
        "Search inventory",
        placeholder=(
            "Search product, SKU, warehouse, batch, "
            "lot, serial number, supplier or origin"
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        status = st.selectbox(
            "Status",
            ["All"] + ITEM_STATUSES,
        )

    with col2:
        warehouse_name = st.selectbox(
            "Warehouse",
            ["All"]
            + get_inventory_warehouse_names(),
        )

    with col3:
        stock_filter = st.selectbox(
            "Stock condition",
            [
                "All",
                "Available Stock",
                "Reorder Required",
                "Out of Stock",
                "Damaged Stock",
            ],
        )

    items = get_inventory_items(
        search=search,
        status=status,
        warehouse_name=warehouse_name,
        stock_filter=stock_filter,
    )

    st.caption(
        f"{len(items)} inventory item(s) found"
    )

    if not items:
        st.info("No inventory items found.")
        return

    st.dataframe(
        [
            {
                "ID": item.id,
                "Product": item.product_name,
                "SKU": item.sku,
                "Warehouse": item.warehouse_name,
                "Location": (
                    item.storage_location or ""
                ),
                "Batch": item.batch_number or "",
                "Lot": item.lot_number or "",
                "Unit": item.unit,
                "On Hand": item.quantity_on_hand,
                "Reserved": item.quantity_reserved,
                "Damaged": item.quantity_damaged,
                "Available": item.available_quantity,
                "Reorder Level": item.reorder_level,
                "Unit Cost": item.unit_cost,
                "Currency": item.currency,
                "Stock Value": item.stock_value,
                "Expiry": item.expiry_date or "",
                "Reorder": (
                    "Yes"
                    if item.needs_reordering
                    else "No"
                ),
                "Status": item.status,
            }
            for item in items
        ],
        hide_index=True,
        width="stretch",
    )

    selected_item = st.selectbox(
        "Select inventory item",
        items,
        format_func=lambda item: (
            f"{item.product_name} — "
            f"{item.sku} — "
            f"{item.warehouse_name}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Available Stock",
        f"{selected_item.available_quantity:g} "
        f"{selected_item.unit}",
    )

    col2.metric(
        "Stock Value",
        f"{selected_item.currency} "
        f"{selected_item.stock_value:,.2f}",
    )

    col3.metric(
        "Reserved",
        f"{selected_item.quantity_reserved:g}",
    )

    col4.metric(
        "Damaged",
        f"{selected_item.quantity_damaged:g}",
    )

    st.markdown("---")
    st.subheader("Stock Movement History")

    movements = get_inventory_movements(
        inventory_item_id=selected_item.id
    )

    if movements:
        st.dataframe(
            [
                {
                    "ID": movement.id,
                    "Date": movement.movement_date,
                    "Type": movement.movement_type,
                    "Quantity": movement.quantity,
                    "Reference Type": (
                        movement.reference_type or ""
                    ),
                    "Reference": (
                        movement.reference_number or ""
                    ),
                    "From": (
                        movement.from_location or ""
                    ),
                    "To": movement.to_location or "",
                    "Reason": movement.reason or "",
                    "Notes": movement.notes or "",
                }
                for movement in movements
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info(
            "No stock movements recorded."
        )

    st.markdown("---")
    st.subheader("Inventory Settings")

    with st.form(
        f"inventory_settings_{selected_item.id}"
    ):
        col1, col2, col3 = st.columns(3)

        with col1:
            reorder_level = st.number_input(
                "Reorder level",
                min_value=0.0,
                value=float(
                    selected_item.reorder_level
                ),
            )

        with col2:
            maximum_stock_level = st.number_input(
                "Maximum stock level",
                min_value=0.0,
                value=float(
                    selected_item.maximum_stock_level
                ),
            )

        with col3:
            unit_cost = st.number_input(
                "Unit cost",
                min_value=0.0,
                value=float(selected_item.unit_cost),
            )

        storage_location = st.text_input(
            "Internal storage location",
            value=(
                selected_item.storage_location
                or ""
            ),
        )

        item_status = st.selectbox(
            "Status",
            ITEM_STATUSES,
            index=(
                ITEM_STATUSES.index(
                    selected_item.status
                )
                if selected_item.status
                in ITEM_STATUSES
                else 0
            ),
        )

        notes = st.text_area(
            "Notes",
            value=selected_item.notes or "",
        )

        update_submitted = (
            st.form_submit_button(
                "Update Inventory Settings",
                type="primary",
                width="stretch",
            )
        )

    if update_submitted:
        update_inventory_settings(
            selected_item.id,
            reorder_level=reorder_level,
            maximum_stock_level=(
                maximum_stock_level
            ),
            unit_cost=unit_cost,
            status=item_status,
            storage_location=storage_location,
            notes=notes,
        )

        st.success(
            "Inventory settings updated."
        )

        st.rerun()

    confirm_delete = st.checkbox(
        f"Confirm deletion of "
        f"{selected_item.product_name} "
        f"from {selected_item.warehouse_name}"
    )

    if st.button(
        "Delete Inventory Item",
        disabled=not confirm_delete,
    ):
        delete_inventory_item(
            selected_item.id
        )

        st.success(
            "Inventory item deleted."
        )

        st.rerun()