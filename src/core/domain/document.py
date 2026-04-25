from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class DocumentType(str, Enum):
    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    DRIVING_LICENCE = "DRIVING_LICENCE"
    PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    BANK_STATEMENT = "BANK_STATEMENT"
    UTILITY_BILL = "UTILITY_BILL"
    CERTIFICATE_OF_INCORPORATION = "CERTIFICATE_OF_INCORPORATION"
    ARTICLES_OF_ASSOCIATION = "ARTICLES_OF_ASSOCIATION"
    SHAREHOLDER_REGISTER = "SHAREHOLDER_REGISTER"
    AUDITED_ACCOUNTS = "AUDITED_ACCOUNTS"
    BOARD_RESOLUTION = "BOARD_RESOLUTION"
    PROOF_OF_AUTHORITY = "PROOF_OF_AUTHORITY"
    SOURCE_OF_FUNDS = "SOURCE_OF_FUNDS"
    TAX_CERTIFICATE = "TAX_CERTIFICATE"
    OTHER = "OTHER"


class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Document:
    case_id: UUID
    applicant_id: UUID
    doc_type: DocumentType
    file_name: str
    storage_ref: str
    id: UUID = field(default_factory=uuid4)
    status: DocumentStatus = DocumentStatus.UPLOADED
    uploaded_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    rejection_reason: Optional[str] = None
    country_of_issue: Optional[str] = None
    document_number: Optional[str] = None
    mime_type: str = "application/pdf"

    def is_expired(self) -> bool:
        if self.expiry_date is None:
            return False
        return date.today() > self.expiry_date

    def verify(self, reviewer_id: str) -> None:
        self.status = DocumentStatus.VERIFIED
        self.verified_at = datetime.utcnow()

    def reject(self, reason: str) -> None:
        self.status = DocumentStatus.REJECTED
        self.rejection_reason = reason

    def is_valid(self) -> bool:
        return self.status == DocumentStatus.VERIFIED and not self.is_expired()
