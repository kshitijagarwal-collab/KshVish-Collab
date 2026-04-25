from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.auth.jwt import Principal, get_current_principal

from .schemas import (
    CaseStatusView,
    CaseSummary,
    DocumentSummary,
    SubmitCaseRequest,
    UploadDocumentRequest,
)
from .service import (
    ApplicantPortalService,
    CaseAccessDenied,
    CaseNotFound,
    InMemoryApplicantPortalService,
    documents_pending,
)


APPLICANT_ROLE = "APPLICANT"

_default_service: ApplicantPortalService = InMemoryApplicantPortalService()


def get_service() -> ApplicantPortalService:
    return _default_service


def require_applicant(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    if APPLICANT_ROLE not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Applicant role required",
        )
    return principal


router = APIRouter(prefix="/portal/applicant", tags=["applicant-portal"])


@router.post(
    "/cases",
    response_model=CaseSummary,
    status_code=status.HTTP_201_CREATED,
)
def submit_case(
    payload: SubmitCaseRequest,
    principal: Annotated[Principal, Depends(require_applicant)],
    service: Annotated[ApplicantPortalService, Depends(get_service)],
) -> CaseSummary:
    case = service.submit_case(
        applicant_subject=principal.subject,
        case_type=payload.case_type,
        country_code=payload.country_code,
        fund_id=payload.fund_id,
    )
    return CaseSummary(
        id=case.id,
        case_type=case.case_type,
        country_code=case.country_code,
        fund_id=case.fund_id,
        status=case.status,
        risk_tier=case.risk_tier,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    principal: Annotated[Principal, Depends(require_applicant)],
    service: Annotated[ApplicantPortalService, Depends(get_service)],
) -> list[CaseSummary]:
    return [
        CaseSummary(
            id=c.id,
            case_type=c.case_type,
            country_code=c.country_code,
            fund_id=c.fund_id,
            status=c.status,
            risk_tier=c.risk_tier,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in service.list_cases_for(principal.subject)
    ]


@router.get("/cases/{case_id}/status", response_model=CaseStatusView)
def case_status(
    case_id: UUID,
    principal: Annotated[Principal, Depends(require_applicant)],
    service: Annotated[ApplicantPortalService, Depends(get_service)],
) -> CaseStatusView:
    try:
        case = service.get_case_for(principal.subject, case_id)
        uploaded = service.documents_for_case(principal.subject, case_id)
    except CaseNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except CaseAccessDenied:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return CaseStatusView(
        id=case.id,
        status=case.status,
        risk_tier=case.risk_tier,
        documents_pending=documents_pending(case, uploaded),
        rejection_reason=case.rejection_reason,
        updated_at=case.updated_at,
    )


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentSummary,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    case_id: UUID,
    payload: UploadDocumentRequest,
    principal: Annotated[Principal, Depends(require_applicant)],
    service: Annotated[ApplicantPortalService, Depends(get_service)],
) -> DocumentSummary:
    try:
        doc = service.attach_document(
            applicant_subject=principal.subject,
            case_id=case_id,
            doc_type=payload.doc_type,
            file_name=payload.file_name,
            storage_ref=payload.storage_ref,
            document_number=payload.document_number,
            country_of_issue=payload.country_of_issue,
        )
    except CaseNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    except CaseAccessDenied:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return DocumentSummary(
        id=doc.id,
        case_id=doc.case_id,
        doc_type=doc.doc_type,
        file_name=doc.file_name,
        uploaded_at=doc.uploaded_at,
    )
