"""Bridge between execution engine and enterprise event bus."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

def _ts()->str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class EnterpriseExecutionEvent:
    execution_id:str
    event_name:str
    payload:dict[str,Any]=field(default_factory=dict)
    occurred_at:str=field(default_factory=_ts)

class EnterpriseExecutionEventBridge:
    def __init__(self)->None:
        self._events:list[EnterpriseExecutionEvent]=[]
    def publish(self,execution_id:str,event_name:str,payload:dict[str,Any]|None=None)->EnterpriseExecutionEvent:
        event=EnterpriseExecutionEvent(execution_id,event_name,payload or {})
        self._events.append(event)
        return event
    def history(self)->tuple[EnterpriseExecutionEvent,...]:
        return tuple(self._events)