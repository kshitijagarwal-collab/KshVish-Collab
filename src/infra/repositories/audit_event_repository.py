from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infra.audit import AuditEvent, AuditEventType
from src.infra.orm import AuditEventORM


class AuditEventRepository:
    """Append-only repository for audit events.

    Deliberately exposes only `add` and read methods — audit history is
    immutable by compliance requirement. There are no update or delete
    methods on this repository, ever.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: AuditEvent) -> None:
        self._session.add(AuditEventORM.from_domain(event))

    def list_for_case(self, case_id: UUID) -> list[AuditEvent]:
        stmt = (
            select(AuditEventORM)
            .where(AuditEventORM.case_id == str(case_id))
            .order_by(AuditEventORM.occurred_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def list_by_event_type(self, event_type: AuditEventType) -> list[AuditEvent]:
        stmt = (
            select(AuditEventORM)
            .where(AuditEventORM.event_type == event_type)
            .order_by(AuditEventORM.occurred_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]
