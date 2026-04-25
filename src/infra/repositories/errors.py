from __future__ import annotations

from uuid import UUID


class RepositoryError(Exception):
    pass


class CaseNotFoundError(RepositoryError):
    def __init__(self, case_id: UUID) -> None:
        super().__init__(f"KYC case {case_id} not found")
        self.case_id = case_id


class DocumentNotFoundError(RepositoryError):
    def __init__(self, doc_id: UUID) -> None:
        super().__init__(f"Document {doc_id} not found")
        self.doc_id = doc_id
