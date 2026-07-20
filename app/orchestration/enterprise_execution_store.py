"""Store for enterprise executions."""
from __future__ import annotations
from threading import RLock
from app.orchestration.enterprise_execution_models import EnterpriseExecution
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError

class EnterpriseExecutionStore:
    def __init__(self)->None:
        self._items:dict[str,EnterpriseExecution]={}
        self._lock=RLock()
    def create(self,item:EnterpriseExecution)->None:
        with self._lock:
            if item.execution_id in self._items:
                raise WorkflowIntegrityError(technical_message="Execution already exists.")
            self._items[item.execution_id]=item
    def get(self,execution_id:str)->EnterpriseExecution:
        with self._lock:
            try:return self._items[execution_id]
            except KeyError:
                raise WorkflowNotFoundError(technical_message="Execution not found.")
    def list_all(self)->tuple[EnterpriseExecution,...]:
        with self._lock:
            return tuple(self._items.values())
_default=EnterpriseExecutionStore()
def get_enterprise_execution_store()->EnterpriseExecutionStore:
    return _default