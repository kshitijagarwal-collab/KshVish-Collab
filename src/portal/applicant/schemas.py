from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.core.domain.document import DocumentType
from src.core.domain.kyc_case import CaseStatus, CaseType, RiskTier


class SubmitCaseRequest(BaseModel):
    case_type: CaseType
    country_code: str = Field(min_length=2, max_length=8)
    fund_id: str = Field(min_length=1, max_length=64)
    applicant_email: str = Field(min_length=3, max_length=256, pattern=r".+@.+\..+")
    applicant_full_name: str = Field(min_length=1, max_length=256)


class CaseSummary(BaseModel):
    id: UUID
    case_type: CaseType
    country_code: str
    fund_id: str
    status: CaseStatus
    risk_tier: Optional[RiskTier]
    created_at: datetime
    updated_at: datetime


class CaseStatusView(BaseModel):
    id: UUID
    status: CaseStatus
    risk_tier: Optional[RiskTier]
    documents_pending: list[DocumentType] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    updated_at: datetime


class UploadDocumentRequest(BaseModel):
    doc_type: DocumentType
    file_name: str = Field(min_length=1, max_length=512)
    storage_ref: str = Field(min_length=1, max_length=1024)
    document_number: Optional[str] = Field(default=None, max_length=128)
    country_of_issue: Optional[str] = Field(default=None, max_length=8)


class DocumentSummary(BaseModel):
    id: UUID
    case_id: UUID
    doc_type: DocumentType
    file_name: str
    uploaded_at: datetime
