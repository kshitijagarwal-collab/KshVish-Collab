from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.infra.audit import AuditEvent, AuditEventType
from src.infra.orm import AuditEventORM, Base


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def test_audit_event_round_trip(session: Session) -> None:
    event = AuditEvent(
        event_type=AuditEventType.CASE_CREATED,
        case_id=uuid4(),
        actor="reviewer-1",
        applicant_id=uuid4(),
        payload={"country": "GB", "fund_id": "FUND-001"},
        ip_address="10.0.0.1",
        session_id="sess-abc",
        occurred_at=datetime(2026, 4, 25, 12, 0, 0),
    )
    session.add(AuditEventORM.from_domain(event))
    session.commit()

    fetched = session.get(AuditEventORM, str(event.id))
    assert fetched is not None
    assert fetched.to_domain() == event


def test_audit_event_minimal_round_trip(session: Session) -> None:
    event = AuditEvent(
        event_type=AuditEventType.CASE_APPROVED,
        case_id=uuid4(),
        actor="system",
        occurred_at=datetime(2026, 4, 25, 12, 0, 0),
    )
    session.add(AuditEventORM.from_domain(event))
    session.commit()

    fetched = session.get(AuditEventORM, str(event.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == event
    assert restored.applicant_id is None
    assert restored.payload == {}
    assert restored.ip_address is None
    assert restored.session_id is None
