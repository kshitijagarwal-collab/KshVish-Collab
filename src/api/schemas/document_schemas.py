from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from src.core.domain.document import DocumentStatus, DocumentType


class CreateDocumentRequest(BaseModel):
    doc_type: DocumentType
    file_name: str
    storage_ref: str
    expiry_date: Optional[date] = None
    country_of_issue: Optional[str] = None
    document_number: Optional[str] = None
    mime_type: str = "application/pdf"


class VerifyDocumentRequest(BaseModel):
    reviewer_id: str


class RejectDocumentRequest(BaseModel):
    reason: str


class DocumentResponse(BaseModel):
    document_id: UUID
    case_id: UUID
    applicant_id: UUID
    doc_type: DocumentType
    status: DocumentStatus
    file_name: str
    uploaded_at: datetime
    verified_at: Optional[datetime]
    expiry_date: Optional[date]
    is_expired: bool
