from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.core.domain.applicant import IndividualApplicant


IDENTITY_DOC_TYPES = {
    DocumentType.PASSPORT,
    DocumentType.NATIONAL_ID,
    DocumentType.DRIVING_LICENCE,
}


@dataclass
class IdentityVerificationResult:
    applicant_id: UUID
    passed: bool
    document_id: Optional[UUID]
    failure_reason: Optional[str] = None
    doc_type: Optional[DocumentType] = None
    doc_expiry: Optional[date] = None


def verify_identity(
    applicant: IndividualApplicant,
    documents: list[Document],
) -> IdentityVerificationResult:
    identity_docs = [
        d for d in documents
        if d.doc_type in IDENTITY_DOC_TYPES and d.applicant_id == applicant.id
    ]

    if not identity_docs:
        return IdentityVerificationResult(
            applicant_id=applicant.id,
            passed=False,
            document_id=None,
            failure_reason="No identity document uploaded",
        )

    verified = [d for d in identity_docs if d.status == DocumentStatus.VERIFIED]
    if not verified:
        return IdentityVerificationResult(
            applicant_id=applicant.id,
            passed=False,
            document_id=identity_docs[0].id,
            failure_reason="Identity document not yet verified",
        )

    valid = [d for d in verified if not d.is_expired()]
    if not valid:
        return IdentityVerificationResult(
            applicant_id=applicant.id,
            passed=False,
            document_id=verified[0].id,
            failure_reason="All identity documents are expired",
        )

    doc = valid[0]
    return IdentityVerificationResult(
        applicant_id=applicant.id,
        passed=True,
        document_id=doc.id,
        doc_type=doc.doc_type,
        doc_expiry=doc.expiry_date,
    )


def required_doc_types_for_country(country_code: str) -> set[DocumentType]:
    from src.config.countries.registry import get_country_rules
    rules = get_country_rules(country_code)
    return rules.required_identity_doc_types
