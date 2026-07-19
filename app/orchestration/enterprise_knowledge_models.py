"""Immutable models for the enterprise knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeEntityType(str, Enum):
    SUPPLIER = "supplier"
    PRODUCT = "product"
    CUSTOMER = "customer"
    SHIPMENT = "shipment"
    RFQ = "rfq"
    QUOTATION = "quotation"
    PURCHASE_ORDER = "purchase_order"
    WAREHOUSE = "warehouse"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    APPROVAL = "approval"
    DOCUMENT = "document"
    PAYMENT = "payment"
    USER = "user"


class KnowledgeRelationshipType(str, Enum):
    SUPPLIES = "supplies"
    REQUESTS = "requests"
    QUOTES_FOR = "quotes_for"
    CONTAINS = "contains"
    SHIPS_TO = "ships_to"
    STORED_AT = "stored_at"
    APPROVES = "approves"
    DEPENDS_ON = "depends_on"
    EXPOSED_TO = "exposed_to"
    ASSOCIATED_WITH = "associated_with"
    REPLACES = "replaces"
    DERIVED_FROM = "derived_from"
    PAID_BY = "paid_by"


@dataclass(frozen=True)
class KnowledgeEntity:
    entity_type: KnowledgeEntityType
    external_id: str
    name: str
    entity_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    version: str = "1.0.0"
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    attributes: dict[str, Any] = dataclass_field(default_factory=dict)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.entity_id or "").strip():
            raise ValueError("Knowledge entity ID is required.")
        if not str(self.external_id or "").strip():
            raise ValueError("Knowledge external ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Knowledge entity name is required.")

        object.__setattr__(self, "entity_id", str(self.entity_id).strip())
        object.__setattr__(self, "external_id", str(self.external_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version or "1.0.0").strip())
        object.__setattr__(self, "attributes", redact_mapping(self.attributes))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "external_id": self.external_id,
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "attributes": redact_mapping(self.attributes),
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class KnowledgeRelationship:
    source_entity_id: str
    target_entity_id: str
    relationship_type: KnowledgeRelationshipType
    relationship_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    weight: float = 1.0
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    attributes: dict[str, Any] = dataclass_field(default_factory=dict)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.relationship_id or "").strip():
            raise ValueError("Relationship ID is required.")
        if not str(self.source_entity_id or "").strip():
            raise ValueError("Source entity ID is required.")
        if not str(self.target_entity_id or "").strip():
            raise ValueError("Target entity ID is required.")
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("Self-referencing relationships are not allowed.")
        if not 0 <= self.weight <= 1:
            raise ValueError("Relationship weight must be between 0 and 1.")

        object.__setattr__(
            self,
            "relationship_id",
            str(self.relationship_id).strip(),
        )
        object.__setattr__(
            self,
            "source_entity_id",
            str(self.source_entity_id).strip(),
        )
        object.__setattr__(
            self,
            "target_entity_id",
            str(self.target_entity_id).strip(),
        )
        object.__setattr__(self, "attributes", redact_mapping(self.attributes))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relationship_type": self.relationship_type.value,
            "weight": self.weight,
            "created_at": self.created_at,
            "attributes": redact_mapping(self.attributes),
            "metadata": redact_mapping(self.metadata),
        }