from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.core.domain.kyc_case import CaseStatus, KYCCase
from src.infra.audit import AuditEvent, AuditEventType, AuditTrail
from src.infra.db import get_session
from src.infra.repositories import (
    CaseRepository,
    DocumentNotFoundError,
    DocumentRepository,
    IndividualApplicantRepository,
)
from src.infra.storage import store_upload

from .extraction import (
    ExtractedDocument,
    extract_identity_fields,
    extract_pdf_text,
)
from .tesseract_ocr import extract_via_tesseract, is_available as tesseract_available
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


class ExtractedFields(BaseModel):
    full_name: Optional[str]
    document_number: Optional[str]
    date_of_birth: Optional[str]
    expiry_date: Optional[str]


class ValidationResult(BaseModel):
    name_matches: Optional[bool]
    dob_matches: Optional[bool]
    expiry_in_future: Optional[bool]
    all_passed: bool


class UploadedDocumentResponse(BaseModel):
    document: DocumentResponse
    extracted: ExtractedFields
    validation: ValidationResult
    extraction_source: str


def _has_useful_fields(extracted: ExtractedDocument) -> bool:
    populated = sum(
        1
        for v in (
            extracted.full_name,
            extracted.document_number,
            extracted.date_of_birth,
            extracted.expiry_date,
        )
        if v is not None
    )
    return populated >= 2


def _validate_against_applicant(
    extracted: ExtractedDocument,
    case: KYCCase,
    session: Session,
) -> ValidationResult:
    raw_applicant = case.metadata.get("applicant_id")
    applicant = (
        IndividualApplicantRepository(session).get(UUID(raw_applicant))
        if raw_applicant
        else None
    )

    name_matches: Optional[bool] = None
    dob_matches: Optional[bool] = None
    if applicant is not None:
        if extracted.full_name is not None:
            name_matches = extracted.full_name.lower() == applicant.full_name.lower()
        if extracted.date_of_birth is not None:
            dob_matches = extracted.date_of_birth == applicant.date_of_birth

    expiry_in_future: Optional[bool] = None
    if extracted.expiry_date is not None:
        from datetime import date as _date

        expiry_in_future = extracted.expiry_date > _date.today()

    checks = [c for c in (name_matches, dob_matches, expiry_in_future) if c is not None]
    return ValidationResult(
        name_matches=name_matches,
        dob_matches=dob_matches,
        expiry_in_future=expiry_in_future,
        all_passed=bool(checks) and all(checks),
    )


@router.post(
    "/{case_id}/documents/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadedDocumentResponse,
)
async def upload_document_file(
    case_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    doc_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
) -> UploadedDocumentResponse:
    case = _load_case_or_404(session, case_id)
    applicant_id = _resolve_applicant_id(case)

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=422, detail="empty file")

    is_pdf = (file.content_type or "").lower() == "application/pdf" or (
        file.filename or ""
    ).lower().endswith(".pdf")

    extracted = ExtractedDocument(
        full_name=None,
        document_number=None,
        date_of_birth=None,
        expiry_date=None,
        raw_text_length=0,
    )
    extraction_source = "none"
    if is_pdf:
        try:
            text = extract_pdf_text(payload)
            extracted = extract_identity_fields(text)
            if _has_useful_fields(extracted):
                extraction_source = "pdf-text"
        except Exception:
            pass

    if extraction_source == "none" and tesseract_available():
        ocr_mime = file.content_type or (
            "application/pdf" if is_pdf else "application/octet-stream"
        )
        ocr_result = extract_via_tesseract(payload, ocr_mime)
        if ocr_result is not None:
            extracted = ocr_result
            extraction_source = "tesseract"

    doc = Document(
        case_id=case_id,
        applicant_id=applicant_id,
        doc_type=doc_type,
        file_name=file.filename or "upload",
        storage_ref="",
        expiry_date=extracted.expiry_date,
        document_number=extracted.document_number,
        mime_type=file.content_type or "application/octet-stream",
    )
    doc.storage_ref = store_upload(doc.id, file.filename or "upload", payload)
    DocumentRepository(session).add(doc)

    if case.status == CaseStatus.INITIATED:
        case.transition(
            CaseStatus.DOCUMENTS_PENDING, actor="api", reason="first document uploaded"
        )
        CaseRepository(session).update(case)

    validation = _validate_against_applicant(extracted, case, session)

    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            case_id=case_id,
            actor="api",
            applicant_id=applicant_id,
            payload={
                "doc_type": doc_type.value,
                "file_name": doc.file_name,
                "extracted": extracted.to_dict(),
                "validation": validation.model_dump(),
                "extraction_source": extraction_source,
            },
        )
    )

    session.commit()

    return UploadedDocumentResponse(
        document=_doc_to_response(doc),
        extracted=ExtractedFields(
            full_name=extracted.full_name,
            document_number=extracted.document_number,
            date_of_birth=(
                extracted.date_of_birth.isoformat() if extracted.date_of_birth else None
            ),
            expiry_date=(
                extracted.expiry_date.isoformat() if extracted.expiry_date else None
            ),
        ),
        validation=validation,
        extraction_source=extraction_source,
    )


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
