from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, JSON, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain.applicant import (
    Address,
    CorporateApplicant,
    IndividualApplicant,
    InvestorClass,
)
from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase, RiskTier

from .base import Base


class KYCCaseORM(Base):
    __tablename__ = "kyc_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_type: Mapped[CaseType] = mapped_column(SAEnum(CaseType), nullable=False)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False)
    fund_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus), nullable=False, default=CaseStatus.INITIATED
    )
    risk_tier: Mapped[Optional[RiskTier]] = mapped_column(SAEnum(RiskTier), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    case_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    @classmethod
    def from_domain(cls, case: KYCCase) -> "KYCCaseORM":
        return cls(
            id=str(case.id),
            case_type=case.case_type,
            country_code=case.country_code,
            fund_id=case.fund_id,
            status=case.status,
            risk_tier=case.risk_tier,
            created_at=case.created_at,
            updated_at=case.updated_at,
            reviewer_id=case.reviewer_id,
            rejection_reason=case.rejection_reason,
            expiry_date=case.expiry_date,
            case_metadata=dict(case.metadata),
        )

    def to_domain(self) -> KYCCase:
        return KYCCase(
            id=UUID(self.id),
            case_type=self.case_type,
            country_code=self.country_code,
            fund_id=self.fund_id,
            status=self.status,
            risk_tier=self.risk_tier,
            created_at=self.created_at,
            updated_at=self.updated_at,
            reviewer_id=self.reviewer_id,
            rejection_reason=self.rejection_reason,
            expiry_date=self.expiry_date,
            metadata=dict(self.case_metadata or {}),
        )


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("kyc_cases.id"), nullable=False
    )
    applicant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType), nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    country_of_issue: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    mime_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="application/pdf"
    )

    @classmethod
    def from_domain(cls, doc: Document) -> "DocumentORM":
        return cls(
            id=str(doc.id),
            case_id=str(doc.case_id),
            applicant_id=str(doc.applicant_id),
            doc_type=doc.doc_type,
            file_name=doc.file_name,
            storage_ref=doc.storage_ref,
            status=doc.status,
            uploaded_at=doc.uploaded_at,
            verified_at=doc.verified_at,
            expiry_date=doc.expiry_date,
            rejection_reason=doc.rejection_reason,
            country_of_issue=doc.country_of_issue,
            document_number=doc.document_number,
            mime_type=doc.mime_type,
        )

    def to_domain(self) -> Document:
        return Document(
            id=UUID(self.id),
            case_id=UUID(self.case_id),
            applicant_id=UUID(self.applicant_id),
            doc_type=self.doc_type,
            file_name=self.file_name,
            storage_ref=self.storage_ref,
            status=self.status,
            uploaded_at=self.uploaded_at,
            verified_at=self.verified_at,
            expiry_date=self.expiry_date,
            rejection_reason=self.rejection_reason,
            country_of_issue=self.country_of_issue,
            document_number=self.document_number,
            mime_type=self.mime_type,
        )


class IndividualApplicantORM(Base):
    __tablename__ = "individual_applicants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    nationality: Mapped[str] = mapped_column(String(8), nullable=False)
    country_of_residence: Mapped[str] = mapped_column(String(8), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    investor_class: Mapped[Optional[InvestorClass]] = mapped_column(
        SAEnum(InvestorClass), nullable=True
    )
    is_pep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_sanctioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_of_funds: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    addr_line1: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    addr_line2: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    addr_city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    addr_state: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    addr_postal_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    addr_country_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    @classmethod
    def from_domain(cls, applicant: IndividualApplicant) -> "IndividualApplicantORM":
        addr = applicant.address
        return cls(
            id=str(applicant.id),
            first_name=applicant.first_name,
            last_name=applicant.last_name,
            middle_name=applicant.middle_name,
            date_of_birth=applicant.date_of_birth,
            nationality=applicant.nationality,
            country_of_residence=applicant.country_of_residence,
            email=applicant.email,
            phone=applicant.phone,
            investor_class=applicant.investor_class,
            is_pep=applicant.is_pep,
            is_sanctioned=applicant.is_sanctioned,
            tax_id=applicant.tax_id,
            source_of_funds=applicant.source_of_funds,
            addr_line1=addr.line1 if addr else None,
            addr_line2=addr.line2 if addr else None,
            addr_city=addr.city if addr else None,
            addr_state=addr.state if addr else None,
            addr_postal_code=addr.postal_code if addr else None,
            addr_country_code=addr.country_code if addr else None,
        )

    def to_domain(self) -> IndividualApplicant:
        address: Optional[Address] = None
        if self.addr_line1 is not None:
            address = Address(
                line1=self.addr_line1,
                city=self.addr_city or "",
                country_code=self.addr_country_code or "",
                postal_code=self.addr_postal_code or "",
                line2=self.addr_line2,
                state=self.addr_state,
            )
        return IndividualApplicant(
            id=UUID(self.id),
            first_name=self.first_name,
            last_name=self.last_name,
            middle_name=self.middle_name,
            date_of_birth=self.date_of_birth,
            nationality=self.nationality,
            country_of_residence=self.country_of_residence,
            email=self.email,
            phone=self.phone,
            address=address,
            investor_class=self.investor_class,
            is_pep=self.is_pep,
            is_sanctioned=self.is_sanctioned,
            tax_id=self.tax_id,
            source_of_funds=self.source_of_funds,
        )


class CorporateApplicantORM(Base):
    __tablename__ = "corporate_applicants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(256), nullable=False)
    trading_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    registration_number: Mapped[str] = mapped_column(String(128), nullable=False)
    country_of_incorporation: Mapped[str] = mapped_column(String(8), nullable=False)
    incorporation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    regulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regulator: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lei_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_sanctioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ubo_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    addr_line1: Mapped[str] = mapped_column(String(256), nullable=False)
    addr_line2: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    addr_city: Mapped[str] = mapped_column(String(128), nullable=False)
    addr_state: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    addr_postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    addr_country_code: Mapped[str] = mapped_column(String(8), nullable=False)

    @classmethod
    def from_domain(cls, applicant: CorporateApplicant) -> "CorporateApplicantORM":
        addr = applicant.registered_address
        return cls(
            id=str(applicant.id),
            legal_name=applicant.legal_name,
            trading_name=applicant.trading_name,
            registration_number=applicant.registration_number,
            country_of_incorporation=applicant.country_of_incorporation,
            incorporation_date=applicant.incorporation_date,
            business_type=applicant.business_type,
            regulated=applicant.regulated,
            regulator=applicant.regulator,
            lei_code=applicant.lei_code,
            tax_id=applicant.tax_id,
            is_sanctioned=applicant.is_sanctioned,
            ubo_complete=applicant.ubo_complete,
            addr_line1=addr.line1,
            addr_line2=addr.line2,
            addr_city=addr.city,
            addr_state=addr.state,
            addr_postal_code=addr.postal_code,
            addr_country_code=addr.country_code,
        )

    def to_domain(self) -> CorporateApplicant:
        return CorporateApplicant(
            id=UUID(self.id),
            legal_name=self.legal_name,
            trading_name=self.trading_name,
            registration_number=self.registration_number,
            country_of_incorporation=self.country_of_incorporation,
            registered_address=Address(
                line1=self.addr_line1,
                line2=self.addr_line2,
                city=self.addr_city,
                state=self.addr_state,
                postal_code=self.addr_postal_code,
                country_code=self.addr_country_code,
            ),
            incorporation_date=self.incorporation_date,
            business_type=self.business_type,
            regulated=self.regulated,
            regulator=self.regulator,
            lei_code=self.lei_code,
            tax_id=self.tax_id,
            is_sanctioned=self.is_sanctioned,
            ubo_complete=self.ubo_complete,
        )
