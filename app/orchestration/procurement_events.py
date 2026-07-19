"""Procurement workflow event model."""
from __future__ import annotations
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from app.observability.redaction import redact_mapping

def utc_timestamp()->str: return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class ProcurementEvent:
    event_type:str
    case_id:str
    actor_id:str=""
    event_id:str=dataclass_field(default_factory=lambda:uuid4().hex)
    occurred_at:str=dataclass_field(default_factory=utc_timestamp)
    data:dict[str,Any]=dataclass_field(default_factory=dict)
    def __post_init__(self)->None:
        if not str(self.event_type or "").strip(): raise ValueError("Procurement event type is required.")
        if not str(self.case_id or "").strip(): raise ValueError("Procurement case ID is required.")
        object.__setattr__(self,"event_type",str(self.event_type).strip())
        object.__setattr__(self,"case_id",str(self.case_id).strip())
        object.__setattr__(self,"actor_id",str(self.actor_id or "").strip())
        object.__setattr__(self,"data",redact_mapping(self.data))
    def as_dict(self)->dict[str,Any]:
        return {"event_id":self.event_id,"event_type":self.event_type,"case_id":self.case_id,"actor_id":self.actor_id,"occurred_at":self.occurred_at,"data":redact_mapping(self.data)}