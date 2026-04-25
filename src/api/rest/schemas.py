from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from src.core.domain.applicant import InvestorClass
from src.core.domain.document import DocumentStatus, DocumentType
from src.core.domain.kyc_case import CaseStatus, CaseType, RiskTier


class AddressIn(BaseModel):
    line1: str = Field(min_length=1, max_length=256)
    city: str = Field(min_length=1, max_length=128)
    country_code: str = Field(min_length=2, max_length=8)
    postal_code: str = Field(min_length=1, max_length=32)
    line2: Optional[str] = Field(default=None, max_length=256)
    state: Optional[str] = Field(default=None, max_length=128)


class IndividualApplicantIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    date_of_birth: date
    nationality: str = Field(min_length=2, max_length=8)
    country_of_residence: str = Field(min_length=2, max_length=8)
    email: EmailStr
    middle_name: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=64)
    address: Optional[AddressIn] = None
    investor_class: Optional[InvestorClass] = None
    tax_id: Optional[str] = Field(default=None, max_length=64)
    source_of_funds: Optional[str] = Field(default=None, max_length=256)


class CorporateApplicantIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=256)
    registration_number: str = Field(min_length=1, max_length=128)
    country_of_incorporation: str = Field(min_length=2, max_length=8)
    registered_address: AddressIn
    trading_name: Optional[str] = Field(default=None, max_length=256)
    incorporation_date: Optional[date] = None
    business_type: Optional[str] = Field(default=None, max_length=128)
    regulated: bool = False
    regulator: Optional[str] = Field(default=None, max_length=128)
    lei_code: Optional[str] = Field(default=None, max_length=20)
    tax_id: Optional[str] = Field(default=None, max_length=64)


class CreateCaseRequest(BaseModel):
    case_type: CaseType
    country_code: str = Field(min_length=2, max_length=8)
    fund_id: str = Field(min_length=1, max_length=64)
    individual: Optional[IndividualApplicantIn] = None
    corporate: Optional[CorporateApplicantIn] = None


class CaseResponse(BaseModel):
    case_id: UUID
    case_type: CaseType
    status: CaseStatus
    country_code: str
    fund_id: str
    risk_tier: Optional[RiskTier]
    reviewer_id: Optional[str]
    rejection_reason: Optional[str]
    applicant_id: Optional[UUID]
    applicant_name: Optional[str]
    created_at: datetime
    updated_at: datetime


class CreateDocumentRequest(BaseModel):
    doc_type: DocumentType
    file_name: str = Field(min_length=1, max_length=512)
    storage_ref: str = Field(min_length=1, max_length=1024)
    expiry_date: Optional[date] = None
    country_of_issue: Optional[str] = Field(default=None, max_length=8)
    document_number: Optional[str] = Field(default=None, max_length=128)
    mime_type: str = Field(default="application/pdf", max_length=64)


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


class VerifyDocumentRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=64)


class RejectDocumentRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)


class SanctionsHitOut(BaseModel):
    list_name: str
    matched_name: str
    match_score: float
    reference: str


class PEPMatchOut(BaseModel):
    matched_name: str
    category: str
    country: str
    position: str
    match_score: float


class ScreeningResponse(BaseModel):
    case_id: UUID
    screened_at: datetime
    identity_passed: bool
    identity_failure: Optional[str]
    sanctions_clear: bool
    sanctions_hits: list[SanctionsHitOut]
    is_pep: bool
    pep_matches: list[PEPMatchOut]
    edd_required: bool
    risk_tier: RiskTier
    weighted_score: float


class ApproveRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=1024)


class RejectRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=1024)


class AuditEventOut(BaseModel):
    event_id: UUID
    case_id: UUID
    event_type: str
    actor: str
    occurred_at: datetime
    payload: dict
