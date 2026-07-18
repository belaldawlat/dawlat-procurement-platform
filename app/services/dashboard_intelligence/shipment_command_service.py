"""Shipment command-center aggregation and exception intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Iterable


class ShipmentCommandStatus(str, Enum):
    ON_TRACK = "On Track"
    ATTENTION = "Attention"
    DELAYED = "Delayed"
    BLOCKED = "Blocked"
    DELIVERED = "Delivered"


@dataclass(frozen=True)
class ShipmentCommandInput:
    shipment_id: str
    reference: str
    supplier_name: str
    customer_name: str
    product_name: str
    origin_port: str
    destination_port: str
    status: str
    etd: str | None
    eta: str | None
    atd: str | None
    ata: str | None
    shipment_value: float
    expected_landed_cost: float
    actual_landed_cost: float | None
    documents_complete: bool
    customs_clearance_complete: bool
    tracking_stale_hours: int
    delay_reason: str | None
    owner: str


@dataclass(frozen=True)
class ShipmentCommandRecord:
    shipment_id: str
    reference: str
    command_status: ShipmentCommandStatus
    days_to_eta: int | None
    delay_days: int
    landed_cost_variance: float
    landed_cost_variance_percent: float
    warnings: tuple[str, ...]
    next_action: str
    owner: str


@dataclass(frozen=True)
class ShipmentCommandSnapshot:
    total_shipments: int
    active_shipments: int
    delivered_shipments: int
    delayed_shipments: int
    blocked_shipments: int
    total_shipment_value: float
    total_expected_landed_cost: float
    total_actual_landed_cost: float
    total_cost_variance: float
    on_time_rate_percent: float
    records: tuple[ShipmentCommandRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ShipmentCommandService:
    """Create shipment control-tower exception views."""

    def build(
        self,
        shipments: Iterable[ShipmentCommandInput],
    ) -> ShipmentCommandSnapshot:
        items = list(shipments)
        records = tuple(self._assess(item) for item in items)

        delivered = sum(
            1
            for record in records
            if record.command_status == ShipmentCommandStatus.DELIVERED
        )
        delayed = sum(
            1
            for record in records
            if record.command_status == ShipmentCommandStatus.DELAYED
        )
        blocked = sum(
            1
            for record in records
            if record.command_status == ShipmentCommandStatus.BLOCKED
        )
        active = len(items) - delivered

        eligible_for_ontime = [
            record
            for record in records
            if record.command_status in {
                ShipmentCommandStatus.DELIVERED,
                ShipmentCommandStatus.DELAYED,
            }
        ]
        on_time = sum(
            1
            for record in eligible_for_ontime
            if record.delay_days == 0
        )
        on_time_rate = (
            on_time / len(eligible_for_ontime) * 100.0
            if eligible_for_ontime
            else 0.0
        )

        actual_cost = sum(
            item.actual_landed_cost
            if item.actual_landed_cost is not None
            else item.expected_landed_cost
            for item in items
        )
        expected_cost = sum(item.expected_landed_cost for item in items)

        return ShipmentCommandSnapshot(
            total_shipments=len(items),
            active_shipments=active,
            delivered_shipments=delivered,
            delayed_shipments=delayed,
            blocked_shipments=blocked,
            total_shipment_value=round(
                sum(item.shipment_value for item in items),
                2,
            ),
            total_expected_landed_cost=round(expected_cost, 2),
            total_actual_landed_cost=round(actual_cost, 2),
            total_cost_variance=round(actual_cost - expected_cost, 2),
            on_time_rate_percent=round(on_time_rate, 2),
            records=tuple(
                sorted(
                    records,
                    key=lambda item: (
                        item.command_status
                        not in {
                            ShipmentCommandStatus.BLOCKED,
                            ShipmentCommandStatus.DELAYED,
                        },
                        -item.delay_days,
                        item.reference,
                    ),
                )
            ),
        )

    def _assess(
        self,
        item: ShipmentCommandInput,
    ) -> ShipmentCommandRecord:
        today = date.today()
        eta = _parse_date(item.eta)
        ata = _parse_date(item.ata)
        warnings: list[str] = []

        delivered = item.status.strip().lower() == "delivered" or ata is not None
        days_to_eta = (eta - today).days if eta is not None else None
        delay_days = 0

        if delivered and eta is not None and ata is not None:
            delay_days = max(0, (ata - eta).days)
        elif not delivered and eta is not None:
            delay_days = max(0, (today - eta).days)

        if not item.documents_complete:
            warnings.append("Shipment documents are incomplete.")
        if item.tracking_stale_hours >= 24:
            warnings.append("Shipment tracking data is stale.")
        if (
            item.status.strip().lower() in {"customs clearance", "arrived at port"}
            and not item.customs_clearance_complete
        ):
            warnings.append("Customs clearance is incomplete.")
        if delay_days > 0:
            warnings.append(
                item.delay_reason or "Shipment has exceeded its ETA."
            )

        actual = (
            item.actual_landed_cost
            if item.actual_landed_cost is not None
            else item.expected_landed_cost
        )
        variance = actual - item.expected_landed_cost
        variance_percent = (
            variance / item.expected_landed_cost * 100.0
            if item.expected_landed_cost > 0
            else 0.0
        )

        blocked = (
            not item.documents_complete
            or (
                item.status.strip().lower()
                in {"customs clearance", "arrived at port"}
                and not item.customs_clearance_complete
            )
        )

        if delivered:
            command_status = ShipmentCommandStatus.DELIVERED
        elif blocked:
            command_status = ShipmentCommandStatus.BLOCKED
        elif delay_days > 0:
            command_status = ShipmentCommandStatus.DELAYED
        elif warnings or (
            days_to_eta is not None
            and days_to_eta <= 3
        ):
            command_status = ShipmentCommandStatus.ATTENTION
        else:
            command_status = ShipmentCommandStatus.ON_TRACK

        next_action = (
            "Complete missing documents or customs requirements."
            if blocked
            else "Escalate delay and refresh recovery ETA."
            if delay_days > 0
            else "Refresh carrier tracking."
            if item.tracking_stale_hours >= 24
            else "Confirm final delivery and actual landed cost."
            if delivered and item.actual_landed_cost is None
            else "Continue active monitoring."
        )

        return ShipmentCommandRecord(
            shipment_id=item.shipment_id,
            reference=item.reference,
            command_status=command_status,
            days_to_eta=days_to_eta,
            delay_days=delay_days,
            landed_cost_variance=round(variance, 2),
            landed_cost_variance_percent=round(variance_percent, 2),
            warnings=tuple(warnings),
            next_action=next_action,
            owner=item.owner,
        )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


_service = ShipmentCommandService()


def get_shipment_command_service() -> ShipmentCommandService:
    return _service