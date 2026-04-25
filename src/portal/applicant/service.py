from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID, uuid4

from src.core.domain.document import Document, DocumentType
from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase, RiskTier


class CaseAccessDenied(Exception):
    pass


class CaseNotFound(Exception):
    pass


class ApplicantPortalService(Protocol):
    def submit_case(
        self,
        applicant_subject: str,
        case_type: CaseType,
        country_code: str,
        fund_id: str,
    ) -> KYCCase: ...

    def list_cases_for(self, applicant_subject: str) -> list[KYCCase]: ...

    def get_case_for(self, applicant_subject: str, case_id: UUID) -> KYCCase: ...

    def attach_document(
        self,
        applicant_subject: str,
        case_id: UUID,
        doc_type: DocumentType,
        file_name: str,
        storage_ref: str,
        document_number: Optional[str],
        country_of_issue: Optional[str],
    ) -> Document: ...

    def documents_for_case(
        self,
        applicant_subject: str,
        case_id: UUID,
    ) -> list[Document]: ...


class InMemoryApplicantPortalService:
    def __init__(self) -> None:
        self._cases: dict[UUID, KYCCase] = {}
        self._owners: dict[UUID, str] = {}
        self._documents: dict[UUID, Document] = {}

    def submit_case(
        self,
        applicant_subject: str,
        case_type: CaseType,
        country_code: str,
        fund_id: str,
    ) -> KYCCase:
        case = KYCCase(
            case_type=case_type,
            country_code=country_code,
            fund_id=fund_id,
        )
        self._cases[case.id] = case
        self._owners[case.id] = applicant_subject
        return case

    def list_cases_for(self, applicant_subject: str) -> list[KYCCase]:
        return [
            self._cases[cid]
            for cid, owner in self._owners.items()
            if owner == applicant_subject
        ]

    def get_case_for(self, applicant_subject: str, case_id: UUID) -> KYCCase:
        case = self._cases.get(case_id)
        if case is None:
            raise CaseNotFound(str(case_id))
        if self._owners.get(case_id) != applicant_subject:
            raise CaseAccessDenied(str(case_id))
        return case

    def attach_document(
        self,
        applicant_subject: str,
        case_id: UUID,
        doc_type: DocumentType,
        file_name: str,
        storage_ref: str,
        document_number: Optional[str],
        country_of_issue: Optional[str],
    ) -> Document:
        case = self.get_case_for(applicant_subject, case_id)
        applicant_id = _applicant_id_from_subject(applicant_subject)
        doc = Document(
            case_id=case.id,
            applicant_id=applicant_id,
            doc_type=doc_type,
            file_name=file_name,
            storage_ref=storage_ref,
            document_number=document_number,
            country_of_issue=country_of_issue,
        )
        self._documents[doc.id] = doc
        if case.status == CaseStatus.INITIATED:
            case.status = CaseStatus.DOCUMENTS_PENDING
            case.updated_at = datetime.utcnow()
        return doc

    def documents_for_case(
        self,
        applicant_subject: str,
        case_id: UUID,
    ) -> list[Document]:
        self.get_case_for(applicant_subject, case_id)
        return [d for d in self._documents.values() if d.case_id == case_id]


_REQUIRED_INDIVIDUAL_DOCS = (DocumentType.PASSPORT, DocumentType.PROOF_OF_ADDRESS)
_REQUIRED_CORPORATE_DOCS = (
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.SHAREHOLDER_REGISTER,
    DocumentType.PROOF_OF_AUTHORITY,
)


def required_documents_for(case_type: CaseType) -> tuple[DocumentType, ...]:
    if case_type == CaseType.INDIVIDUAL:
        return _REQUIRED_INDIVIDUAL_DOCS
    return _REQUIRED_CORPORATE_DOCS


def documents_pending(case: KYCCase, uploaded: list[Document]) -> list[DocumentType]:
    have = {d.doc_type for d in uploaded}
    return [t for t in required_documents_for(case.case_type) if t not in have]


def _applicant_id_from_subject(subject: str) -> UUID:
    try:
        return UUID(subject)
    except ValueError:
        return uuid4()
