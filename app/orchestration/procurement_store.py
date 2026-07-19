"""Thread-safe storage for enterprise procurement cases."""
from __future__ import annotations
import threading
from app.orchestration.exceptions import WorkflowIntegrityError, WorkflowNotFoundError
from app.orchestration.procurement_models import ProcurementCase

class InMemoryProcurementStore:
    def __init__(self)->None:
        self._cases={}
        self._lock=threading.RLock()
    def create(self,case:ProcurementCase)->ProcurementCase:
        if not isinstance(case,ProcurementCase): raise TypeError("Procurement store requires a ProcurementCase.")
        with self._lock:
            if case.case_id in self._cases: raise WorkflowIntegrityError(technical_message=f"Procurement case {case.case_id!r} already exists.")
            self._cases[case.case_id]=case
        return case
    def get(self,case_id:str)->ProcurementCase:
        cleaned=str(case_id or "").strip()
        if not cleaned: raise ValueError("Procurement case ID is required.")
        with self._lock: case=self._cases.get(cleaned)
        if case is None: raise WorkflowNotFoundError(technical_message=f"Procurement case {cleaned!r} was not found.")
        return case
    def save(self,case:ProcurementCase)->ProcurementCase:
        with self._lock:
            if case.case_id not in self._cases: raise WorkflowNotFoundError(technical_message=f"Procurement case {case.case_id!r} was not found.")
            self._cases[case.case_id]=case
        return case
    def list_cases(self)->tuple[ProcurementCase,...]:
        with self._lock: return tuple(self._cases[k] for k in sorted(self._cases))
    def clear(self)->None:
        with self._lock: self._cases.clear()

_default_procurement_store=InMemoryProcurementStore()
def get_procurement_store()->InMemoryProcurementStore: return _default_procurement_store