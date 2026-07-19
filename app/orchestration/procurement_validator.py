"""Validation for enterprise procurement cases."""
from __future__ import annotations
from dataclasses import dataclass
from app.orchestration.procurement_models import ProcurementCase

@dataclass(frozen=True)
class ProcurementValidationIssue:
    code:str
    message:str
    field_name:str=""

@dataclass(frozen=True)
class ProcurementValidationResult:
    valid:bool
    issues:tuple[ProcurementValidationIssue,...]

class ProcurementValidator:
    def validate(self,case:ProcurementCase)->ProcurementValidationResult:
        issues=[]
        if not case.case_id: issues.append(ProcurementValidationIssue("CASE_ID_REQUIRED","Procurement case ID is required.","case_id"))
        ids=[q.quotation_id for q in case.quotations]
        if len(ids)!=len(set(ids)): issues.append(ProcurementValidationIssue("DUPLICATE_QUOTATION_ID","Procurement quotation IDs must be unique.","quotations"))
        if case.selected_quotation_id and case.selected_quotation is None:
            issues.append(ProcurementValidationIssue("UNKNOWN_SELECTED_QUOTATION","Selected quotation does not exist in the case.","selected_quotation_id"))
        ordered=tuple(sorted(issues,key=lambda x:(x.code,x.field_name)))
        return ProcurementValidationResult(valid=not ordered,issues=ordered)