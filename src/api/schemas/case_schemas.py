from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from src.core.domain.kyc_case import CaseStatus, CaseType, RiskTier


class AddressSchema(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: str
    country_code: str


class IndividualApplicantSchema(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    nationality: str = Field(min_length=2, max_length=2)
    country_of_residence: str = Field(min_length=2, max_length=2)
    email: str
    phone: Optional[str] = None
    address: Optional[AddressSchema] = None
    source_of_funds: Optional[str] = None


class CorporateApplicantSchema(BaseModel):
    legal_name: str
    registration_number: str
    country_of_incorporation: str = Field(min_length=2, max_length=2)
    registered_address: AddressSchema
    trading_name: Optional[str] = None
    lei_code: Optional[str] = None
    tax_id: Optional[str] = None


class CreateCaseRequest(BaseModel):
    case_type: CaseType
    country_code: str = Field(min_length=2, max_length=2)
    fund_id: str
    individual: Optional[IndividualApplicantSchema] = None
    corporate: Optional[CorporateApplicantSchema] = None


class CaseResponse(BaseModel):
    case_id: UUID
    status: CaseStatus
    case_type: CaseType
    country_code: str
    fund_id: str
    risk_tier: Optional[RiskTier]
    reviewer_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ApproveRequest(BaseModel):
    reviewer_id: str


class RejectRequest(BaseModel):
    reviewer_id: str
    reason: str


class RequestInfoRequest(BaseModel):
    reviewer_id: str
    reason: str
