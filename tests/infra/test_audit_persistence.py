from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.infra.audit import AuditEvent, AuditEventType, AuditTrail
from src.infra.orm import Base


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _event(case_id, minute: int = 0) -> AuditEvent:
    return AuditEvent(
        event_type=AuditEventType.CASE_CREATED,
        case_id=case_id,
        actor="reviewer-1",
        occurred_at=datetime(2026, 4, 25, 12, minute, 0),
    )


def test_audit_trail_in_memory_mode_still_works() -> None:
    """No session = legacy in-memory behavior. Backward compat."""
    trail = AuditTrail()
    case_id = uuid4()
    event = _event(case_id)
    trail.record(event)

    history = trail.get_case_history(case_id)
    assert history == [event]


def test_audit_trail_persists_to_db_when_session_provided(session: Session) -> None:
    trail = AuditTrail(session=session)
    case_id = uuid4()
    event = _event(case_id)
    trail.record(event)
    session.commit()

    # New trail instance reading from DB sees the event.
    fresh_trail = AuditTrail(session=session)
    history = fresh_trail.get_case_history(case_id)
    assert [e.id for e in history] == [event.id]


def test_audit_trail_db_mode_returns_chronological_history(session: Session) -> None:
    trail = AuditTrail(session=session)
    case_id = uuid4()
    later = _event(case_id, minute=5)
    earlier = _event(case_id, minute=1)
    trail.record(later)
    trail.record(earlier)
    session.commit()

    history = trail.get_case_history(case_id)
    assert [e.id for e in history] == [earlier.id, later.id]


def test_audit_trail_does_not_commit_session(session: Session) -> None:
    """Caller controls unit of work — record() stages, doesn't commit."""
    trail = AuditTrail(session=session)
    case_id = uuid4()
    trail.record(_event(case_id))
    # No explicit commit — rollback should drop the staged event.
    session.rollback()

    fresh_trail = AuditTrail(session=session)
    assert fresh_trail.get_case_history(case_id) == []
