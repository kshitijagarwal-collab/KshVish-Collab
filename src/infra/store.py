from __future__ import annotations
from typing import Union
from uuid import UUID

from src.core.domain.applicant import CorporateApplicant, IndividualApplicant
from src.core.domain.document import Document
from src.core.domain.kyc_case import KYCCase
from src.infra.audit import AuditEvent

_cases: dict[str, KYCCase] = {}
_applicants: dict[str, Union[IndividualApplicant, CorporateApplicant]] = {}
_documents: dict[str, list[Document]] = {}
_audit: dict[str, list[AuditEvent]] = {}


def save_case(case: KYCCase) -> None:
    _cases[str(case.id)] = case


def get_case(case_id: UUID) -> KYCCase | None:
    return _cases.get(str(case_id))


def save_applicant(applicant: IndividualApplicant | CorporateApplicant) -> None:
    _applicants[str(applicant.id)] = applicant


def get_applicant(applicant_id: UUID) -> IndividualApplicant | CorporateApplicant | None:
    return _applicants.get(str(applicant_id))


def add_document(case_id: UUID, doc: Document) -> None:
    key = str(case_id)
    _documents.setdefault(key, []).append(doc)


def get_documents(case_id: UUID) -> list[Document]:
    return _documents.get(str(case_id), [])


def save_audit_event(case_id: UUID, event: AuditEvent) -> None:
    key = str(case_id)
    _audit.setdefault(key, []).append(event)


def get_audit_events(case_id: UUID) -> list[AuditEvent]:
    return _audit.get(str(case_id), [])
