from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.domain.document import Document, DocumentStatus
from src.core.domain.kyc_case import CaseStatus, KYCCase
from src.infra.audit import AuditEvent, AuditEventType, AuditTrail
from src.infra.db import get_session
from src.infra.repositories import (
    CaseRepository,
    DocumentNotFoundError,
    DocumentRepository,
)

from .schemas import (
    CreateDocumentRequest,
    DocumentResponse,
    RejectDocumentRequest,
    VerifyDocumentRequest,
)

router = APIRouter(prefix="/cases", tags=["Documents"])


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        document_id=doc.id,
        case_id=doc.case_id,
        applicant_id=doc.applicant_id,
        doc_type=doc.doc_type,
        status=doc.status,
        file_name=doc.file_name,
        uploaded_at=doc.uploaded_at,
        verified_at=doc.verified_at,
        expiry_date=doc.expiry_date,
        is_expired=doc.is_expired(),
    )


def _load_case_or_404(session: Session, case_id: UUID) -> KYCCase:
    case = CaseRepository(session).get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


def _resolve_applicant_id(case: KYCCase) -> UUID:
    raw = case.metadata.get("applicant_id")
    if not raw:
        raise HTTPException(
            status_code=422, detail="case has no applicant attached"
        )
    return UUID(raw)


@router.post(
    "/{case_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentResponse,
)
def upload_document(
    case_id: UUID,
    body: CreateDocumentRequest,
    session: Annotated[Session, Depends(get_session)],
) -> DocumentResponse:
    case = _load_case_or_404(session, case_id)
    applicant_id = _resolve_applicant_id(case)

    doc = Document(
        case_id=case_id,
        applicant_id=applicant_id,
        doc_type=body.doc_type,
        file_name=body.file_name,
        storage_ref=body.storage_ref,
        expiry_date=body.expiry_date,
        country_of_issue=body.country_of_issue,
        document_number=body.document_number,
        mime_type=body.mime_type,
    )
    DocumentRepository(session).add(doc)

    if case.status == CaseStatus.INITIATED:
        case.transition(CaseStatus.DOCUMENTS_PENDING, actor="api", reason="first document uploaded")
        CaseRepository(session).update(case)

    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            case_id=case_id,
            actor="api",
            applicant_id=applicant_id,
            payload={"doc_type": doc.doc_type.value, "file_name": doc.file_name},
        )
    )

    session.commit()
    return _doc_to_response(doc)


@router.get("/{case_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    case_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[DocumentResponse]:
    _load_case_or_404(session, case_id)
    docs = DocumentRepository(session).list_for_case(case_id)
    return [_doc_to_response(d) for d in docs]


@router.patch(
    "/{case_id}/documents/{document_id}/verify",
    response_model=DocumentResponse,
)
def verify_document(
    case_id: UUID,
    document_id: UUID,
    body: VerifyDocumentRequest,
    session: Annotated[Session, Depends(get_session)],
) -> DocumentResponse:
    repo = DocumentRepository(session)
    doc = repo.get(document_id)
    if doc is None or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    doc.verify(reviewer_id=body.reviewer_id)
    try:
        repo.update(doc)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.DOCUMENT_VERIFIED,
            case_id=case_id,
            actor=body.reviewer_id,
            applicant_id=doc.applicant_id,
            payload={"document_id": str(document_id)},
        )
    )

    session.commit()
    return _doc_to_response(doc)


@router.patch(
    "/{case_id}/documents/{document_id}/reject",
    response_model=DocumentResponse,
)
def reject_document(
    case_id: UUID,
    document_id: UUID,
    body: RejectDocumentRequest,
    session: Annotated[Session, Depends(get_session)],
) -> DocumentResponse:
    repo = DocumentRepository(session)
    doc = repo.get(document_id)
    if doc is None or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    doc.reject(reason=body.reason)
    try:
        repo.update(doc)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.DOCUMENT_REJECTED,
            case_id=case_id,
            actor="api",
            applicant_id=doc.applicant_id,
            payload={"document_id": str(document_id), "reason": body.reason},
        )
    )

    session.commit()
    assert doc.status == DocumentStatus.REJECTED
    return _doc_to_response(doc)
