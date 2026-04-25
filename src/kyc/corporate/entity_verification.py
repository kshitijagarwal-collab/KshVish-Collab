from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.core.domain.applicant import CorporateApplicant
from src.core.domain.document import Document, DocumentStatus, DocumentType


INCORPORATION_DOC_TYPES = {
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.ARTICLES_OF_ASSOCIATION,
}


@dataclass
class EntityVerificationResult:
    applicant_id: UUID
    verified_at: datetime
    passed: bool
    failure_reason: Optional[str] = None
    registry_confirmed: bool = False
    is_regulated_entity: bool = False
    regulator_reference: Optional[str] = None


def verify_entity(
    applicant: CorporateApplicant,
    documents: list[Document],
) -> EntityVerificationResult:
    now = datetime.utcnow()

    inc_docs = [
        d for d in documents
        if d.doc_type in INCORPORATION_DOC_TYPES
        and d.applicant_id == applicant.id
        and d.status == DocumentStatus.VERIFIED
    ]

    if not inc_docs:
        return EntityVerificationResult(
            applicant_id=applicant.id,
            verified_at=now,
            passed=False,
            failure_reason="Missing verified incorporation documents",
        )

    registry_ok = _check_company_registry(applicant)
    if not registry_ok:
        return EntityVerificationResult(
            applicant_id=applicant.id,
            verified_at=now,
            passed=False,
            failure_reason="Entity not found or details mismatch in company registry",
        )

    return EntityVerificationResult(
        applicant_id=applicant.id,
        verified_at=now,
        passed=True,
        registry_confirmed=True,
        is_regulated_entity=applicant.regulated,
        regulator_reference=applicant.regulator,
    )


def _check_company_registry(applicant: CorporateApplicant) -> bool:
    # Integration point: Companies House (UK), SEC (US), MCA (India), etc.
    return True
