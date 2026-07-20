"""Registry for enterprise execution handlers."""
from __future__ import annotations
from collections.abc import Callable
from threading import RLock
from typing import Any
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError

EnterpriseExecutionHandler = Callable[[dict[str, Any]], dict[str, Any]]

class EnterpriseExecutionRegistry:
    def __init__(self)->None:
        self._handlers:dict[str,EnterpriseExecutionHandler]={}
        self._lock=RLock()
    def register(self,name:str,handler:EnterpriseExecutionHandler)->None:
        key=name.strip()
        with self._lock:
            if key in self._handlers:
                raise WorkflowIntegrityError(technical_message=f"Handler {key!r} already registered.")
            self._handlers[key]=handler
    def get(self,name:str)->EnterpriseExecutionHandler:
        key=name.strip()
        with self._lock:
            if key not in self._handlers:
                raise WorkflowNotFoundError(technical_message=f"Handler {key!r} not found.")
            return self._handlers[key]
    def list_handlers(self)->tuple[str,...]:
        with self._lock:
            return tuple(sorted(self._handlers))
_default=EnterpriseExecutionRegistry()
def get_enterprise_execution_registry()->EnterpriseExecutionRegistry:
    return _default