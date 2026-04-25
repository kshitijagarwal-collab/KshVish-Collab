from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.domain.applicant import ApplicantType, InvestorClass
from src.core.domain.document import DocumentStatus, DocumentType
from src.core.domain.kyc_case import CaseStatus, CaseType, RiskTier
from src.infra.audit import AuditEventType
from src.infra.database import Base


class KYCCaseORM(Base):
    __tablename__ = "kyc_cases"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_type: Mapped[CaseType] = mapped_column(String(20), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    fund_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[CaseStatus] = mapped_column(
        String(32), nullable=False, default=CaseStatus.INITIATED, index=True
    )
    risk_tier: Mapped[Optional[RiskTier]] = mapped_column(String(16), nullable=True)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    case_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    documents: Mapped[list["DocumentORM"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_kyc_cases_status_country", "status", "country_code"),
    )


class ApplicantORM(Base):
    __tablename__ = "applicants"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    applicant_type: Mapped[ApplicantType] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __mapper_args__ = {
        "polymorphic_on": "applicant_type",
        "polymorphic_identity": "BASE",
    }


class IndividualApplicantORM(ApplicantORM):
    __tablename__ = "individual_applicants"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"), primary_key=True
    )
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    nationality: Mapped[str] = mapped_column(String(2), nullable=False)
    country_of_residence: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    investor_class: Mapped[Optional[InvestorClass]] = mapped_column(String(32), nullable=True)
    is_pep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_sanctioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_of_funds: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __mapper_args__ = {"polymorphic_identity": ApplicantType.INDIVIDUAL.value}


class CorporateApplicantORM(ApplicantORM):
    __tablename__ = "corporate_applicants"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"), primary_key=True
    )
    legal_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    trading_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    registration_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country_of_incorporation: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    registered_address: Mapped[dict] = mapped_column(JSON, nullable=False)
    incorporation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    regulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regulator: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lei_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_sanctioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ubo_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __mapper_args__ = {"polymorphic_identity": ApplicantType.CORPORATE.value}


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("kyc_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applicant_id: Mapped[UUID] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_type: Mapped[DocumentType] = mapped_column(String(48), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        String(20), nullable=False, default=DocumentStatus.UPLOADED, index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_of_issue: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="application/pdf")

    case: Mapped["KYCCaseORM"] = relationship(back_populates="documents")


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[AuditEventType] = mapped_column(String(48), nullable=False, index=True)
    case_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    applicant_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_audit_events_case_occurred", "case_id", "occurred_at"),
    )


__all__ = [
    "ApplicantORM",
    "AuditEventORM",
    "CorporateApplicantORM",
    "DocumentORM",
    "IndividualApplicantORM",
    "KYCCaseORM",
]
