from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.domain.document import Document, DocumentStatus
from src.infra.orm import DocumentORM

from .errors import DocumentNotFoundError


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, doc: Document) -> None:
        self._session.add(DocumentORM.from_domain(doc))

    def get(self, doc_id: UUID) -> Optional[Document]:
        row = self._session.get(DocumentORM, str(doc_id))
        return row.to_domain() if row else None

    def list_for_case(self, case_id: UUID) -> list[Document]:
        stmt = select(DocumentORM).where(DocumentORM.case_id == str(case_id))
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def list_by_status(self, status: DocumentStatus) -> list[Document]:
        stmt = select(DocumentORM).where(DocumentORM.status == status)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def update(self, doc: Document) -> Document:
        if self._session.get(DocumentORM, str(doc.id)) is None:
            raise DocumentNotFoundError(doc.id)
        self._session.merge(DocumentORM.from_domain(doc))
        return doc
