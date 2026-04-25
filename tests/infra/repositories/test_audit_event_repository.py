from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.infra.audit import AuditEvent, AuditEventType
from src.infra.orm import Base
from src.infra.repositories import AuditEventRepository


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _event(
    case_id: UUID,
    event_type: AuditEventType = AuditEventType.CASE_CREATED,
    minute: int = 0,
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        case_id=case_id,
        actor="actor-1",
        occurred_at=datetime(2026, 4, 25, 12, minute, 0),
    )


def test_add_and_list_for_case(session: Session) -> None:
    repo = AuditEventRepository(session)
    case_id = uuid4()
    e1 = _event(case_id, minute=1)
    e2 = _event(case_id, AuditEventType.CASE_STATUS_CHANGED, minute=2)
    repo.add(e1)
    repo.add(e2)
    session.commit()

    history = repo.list_for_case(case_id)
    assert [e.id for e in history] == [e1.id, e2.id]


def test_list_for_case_returns_chronological_order(session: Session) -> None:
    repo = AuditEventRepository(session)
    case_id = uuid4()
    later = _event(case_id, minute=5)
    earlier = _event(case_id, minute=1)
    repo.add(later)
    repo.add(earlier)
    session.commit()

    history = repo.list_for_case(case_id)
    assert history[0].id == earlier.id
    assert history[1].id == later.id


def test_list_for_case_isolates_by_case(session: Session) -> None:
    repo = AuditEventRepository(session)
    case_a = uuid4()
    case_b = uuid4()
    a_event = _event(case_a)
    b_event = _event(case_b)
    repo.add(a_event)
    repo.add(b_event)
    session.commit()

    a_history = repo.list_for_case(case_a)
    assert {e.id for e in a_history} == {a_event.id}


def test_list_by_event_type_filters_correctly(session: Session) -> None:
    repo = AuditEventRepository(session)
    case_id = uuid4()
    created = _event(case_id, AuditEventType.CASE_CREATED, minute=1)
    approved = _event(case_id, AuditEventType.CASE_APPROVED, minute=2)
    rejected = _event(case_id, AuditEventType.CASE_REJECTED, minute=3)
    repo.add(created)
    repo.add(approved)
    repo.add(rejected)
    session.commit()

    approvals = repo.list_by_event_type(AuditEventType.CASE_APPROVED)
    assert [e.id for e in approvals] == [approved.id]


def test_repository_does_not_expose_update_or_delete() -> None:
    """Audit events are append-only by compliance requirement."""
    assert not hasattr(AuditEventRepository, "update")
    assert not hasattr(AuditEventRepository, "delete")
    assert not hasattr(AuditEventRepository, "remove")
