"""Event handlers connecting GPNI to the enterprise event bus."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from services.network_intelligence.gpni_audit_service import (
    get_gpni_audit_service,
)

@dataclass(frozen=True)
class GPNIEventHandlerRegistration:
    event_name: str
    handler_name: str

class GPNIEventHandlers:
    def __init__(self) -> None:
        self._registered = False
        self._registrations: list[GPNIEventHandlerRegistration] = []

    def register(
        self,
        subscribe: Callable[[str, Callable[[dict[str, Any]], None]], Any],
    ) -> tuple[GPNIEventHandlerRegistration, ...]:
        if self._registered:
            return tuple(self._registrations)
        handlers = {
            "demand.verified": self.handle_demand_verified,
            "supplier.verified": self.handle_supplier_verified,
            "match.approved": self.handle_match_approved,
            "buyer.final_approval": self.handle_buyer_approval,
            "payment.funds_cleared": self.handle_funds_cleared,
            "contract.activated": self.handle_contract_activated,
            "shipment.delayed": self.handle_shipment_delayed,
        }
        for event_name, handler in handlers.items():
            subscribe(event_name, handler)
            self._registrations.append(
                GPNIEventHandlerRegistration(
                    event_name=event_name,
                    handler_name=handler.__name__,
                )
            )
        self._registered = True
        return tuple(self._registrations)

    def _audit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        case_id = str(
            payload.get("case_id")
            or payload.get("workflow_id")
            or payload.get("source_record_id")
            or "UNKNOWN"
        )
        get_gpni_audit_service().record(
            case_id=case_id,
            event_name=event_name,
            actor=str(payload.get("actor") or "Enterprise Event Bus"),
            stage=str(payload.get("stage") or "Event Processing"),
            decision=str(payload.get("decision") or "Recorded"),
            details=payload,
        )

    def handle_demand_verified(self, payload: dict[str, Any]) -> None:
        self._audit_event("Demand Verified", payload)

    def handle_supplier_verified(self, payload: dict[str, Any]) -> None:
        self._audit_event("Supplier Verified", payload)

    def handle_match_approved(self, payload: dict[str, Any]) -> None:
        self._audit_event("Match Approved", payload)

    def handle_buyer_approval(self, payload: dict[str, Any]) -> None:
        self._audit_event("Buyer Final Approval", payload)

    def handle_funds_cleared(self, payload: dict[str, Any]) -> None:
        self._audit_event("Buyer Funds Cleared", payload)

    def handle_contract_activated(self, payload: dict[str, Any]) -> None:
        self._audit_event("Contract Activated", payload)

    def handle_shipment_delayed(self, payload: dict[str, Any]) -> None:
        self._audit_event("Shipment Delayed", payload)

_handlers = GPNIEventHandlers()

def register_gpni_event_handlers(
    subscribe: Callable[[str, Callable[[dict[str, Any]], None]], Any],
) -> tuple[GPNIEventHandlerRegistration, ...]:
    return _handlers.register(subscribe)