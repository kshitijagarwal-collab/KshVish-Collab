from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.document_schemas import (
    CreateDocumentRequest,
    DocumentResponse,
    RejectDocumentRequest,
    VerifyDocumentRequest,
)
from src.core.domain.document import Document
from src.infra import store

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


@router.post("/{case_id}/documents", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
def upload_document(case_id: UUID, body: CreateDocumentRequest) -> DocumentResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    applicants = [store.get_applicant(aid) for aid in _applicant_ids_for_case(case_id)]
    if not applicants or applicants[0] is None:
        raise HTTPException(status_code=422, detail="No applicant found for this case")

    doc = Document(
        case_id=case_id,
        applicant_id=applicants[0].id,
        doc_type=body.doc_type,
        file_name=body.file_name,
        storage_ref=body.storage_ref,
        expiry_date=body.expiry_date,
        country_of_issue=body.country_of_issue,
        document_number=body.document_number,
        mime_type=body.mime_type,
    )
    store.add_document(case_id, doc)
    return _doc_to_response(doc)


@router.get("/{case_id}/documents", response_model=list[DocumentResponse])
def list_documents(case_id: UUID) -> list[DocumentResponse]:
    if not store.get_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return [_doc_to_response(d) for d in store.get_documents(case_id)]


@router.patch("/{case_id}/documents/{document_id}/verify", response_model=DocumentResponse)
def verify_document(case_id: UUID, document_id: UUID, body: VerifyDocumentRequest) -> DocumentResponse:
    doc = _get_document(case_id, document_id)
    doc.verify(reviewer_id=body.reviewer_id)
    return _doc_to_response(doc)


@router.patch("/{case_id}/documents/{document_id}/reject", response_model=DocumentResponse)
def reject_document(case_id: UUID, document_id: UUID, body: RejectDocumentRequest) -> DocumentResponse:
    doc = _get_document(case_id, document_id)
    doc.reject(reason=body.reason)
    return _doc_to_response(doc)


def _get_document(case_id: UUID, document_id: UUID) -> Document:
    docs = store.get_documents(case_id)
    for doc in docs:
        if doc.id == document_id:
            return doc
    raise HTTPException(status_code=404, detail=f"Document {document_id} not found")


def _applicant_ids_for_case(case_id: UUID) -> list[UUID]:
    from src.infra.store import _applicants
    return [UUID(k) for k in _applicants]
