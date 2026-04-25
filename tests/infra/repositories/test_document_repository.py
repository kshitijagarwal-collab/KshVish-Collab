from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.core.domain.kyc_case import CaseType, KYCCase
from src.infra.orm import Base
from src.infra.repositories import (
    CaseRepository,
    DocumentNotFoundError,
    DocumentRepository,
)


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _seed_case(session: Session, case_id: UUID) -> None:
    parent = KYCCase(
        case_type=CaseType.INDIVIDUAL,
        country_code="GB",
        fund_id="FUND-001",
        id=case_id,
        created_at=datetime(2026, 4, 25, 12, 0, 0),
        updated_at=datetime(2026, 4, 25, 12, 0, 0),
    )
    CaseRepository(session).add(parent)


def _new_doc(
    case_id: UUID,
    status: DocumentStatus = DocumentStatus.UPLOADED,
    doc_type: DocumentType = DocumentType.PASSPORT,
) -> Document:
    return Document(
        case_id=case_id,
        applicant_id=uuid4(),
        doc_type=doc_type,
        file_name="doc.pdf",
        storage_ref="s3://bucket/x",
        status=status,
        uploaded_at=datetime(2026, 4, 25, 12, 0, 0),
    )


def test_add_and_get_round_trip(session: Session) -> None:
    case_id = uuid4()
    _seed_case(session, case_id)
    repo = DocumentRepository(session)

    doc = _new_doc(case_id)
    repo.add(doc)
    session.commit()

    fetched = repo.get(doc.id)
    assert fetched == doc


def test_get_missing_returns_none(session: Session) -> None:
    repo = DocumentRepository(session)
    assert repo.get(uuid4()) is None


def test_list_for_case_returns_only_that_cases_documents(session: Session) -> None:
    case_a = uuid4()
    case_b = uuid4()
    _seed_case(session, case_a)
    _seed_case(session, case_b)
    repo = DocumentRepository(session)

    a1 = _new_doc(case_a)
    a2 = _new_doc(case_a, doc_type=DocumentType.PROOF_OF_ADDRESS)
    b1 = _new_doc(case_b)
    repo.add(a1)
    repo.add(a2)
    repo.add(b1)
    session.commit()

    a_docs = repo.list_for_case(case_a)
    assert {d.id for d in a_docs} == {a1.id, a2.id}

    b_docs = repo.list_for_case(case_b)
    assert {d.id for d in b_docs} == {b1.id}


def test_list_by_status_filters_correctly(session: Session) -> None:
    case_id = uuid4()
    _seed_case(session, case_id)
    repo = DocumentRepository(session)

    uploaded = _new_doc(case_id, status=DocumentStatus.UPLOADED)
    verified = _new_doc(case_id, status=DocumentStatus.VERIFIED)
    rejected = _new_doc(case_id, status=DocumentStatus.REJECTED)
    repo.add(uploaded)
    repo.add(verified)
    repo.add(rejected)
    session.commit()

    results = repo.list_by_status(DocumentStatus.VERIFIED)
    assert [d.id for d in results] == [verified.id]


def test_update_persists_changes(session: Session) -> None:
    case_id = uuid4()
    _seed_case(session, case_id)
    repo = DocumentRepository(session)

    doc = _new_doc(case_id, status=DocumentStatus.UPLOADED)
    repo.add(doc)
    session.commit()

    doc.status = DocumentStatus.VERIFIED
    doc.verified_at = datetime(2026, 4, 26, 9, 0, 0)
    repo.update(doc)
    session.commit()

    refreshed = repo.get(doc.id)
    assert refreshed is not None
    assert refreshed.status == DocumentStatus.VERIFIED
    assert refreshed.verified_at == datetime(2026, 4, 26, 9, 0, 0)


def test_update_missing_raises(session: Session) -> None:
    repo = DocumentRepository(session)
    doc = _new_doc(uuid4())
    with pytest.raises(DocumentNotFoundError) as exc:
        repo.update(doc)
    assert exc.value.doc_id == doc.id
