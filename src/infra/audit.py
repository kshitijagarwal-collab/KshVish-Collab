from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session


class AuditEventType(str, Enum):
    CASE_CREATED = "CASE_CREATED"
    CASE_STATUS_CHANGED = "CASE_STATUS_CHANGED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    SANCTIONS_SCREENED = "SANCTIONS_SCREENED"
    PEP_SCREENED = "PEP_SCREENED"
    RISK_SCORED = "RISK_SCORED"
    UBO_RESOLVED = "UBO_RESOLVED"
    CASE_APPROVED = "CASE_APPROVED"
    CASE_REJECTED = "CASE_REJECTED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    DATA_ACCESSED = "DATA_ACCESSED"
    DATA_DELETED = "DATA_DELETED"


@dataclass
class AuditEvent:
    event_type: AuditEventType
    case_id: UUID
    actor: str
    id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    applicant_id: Optional[UUID] = None
    payload: dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "case_id": str(self.case_id),
            "actor": self.actor,
            "occurred_at": self.occurred_at.isoformat(),
            "applicant_id": str(self.applicant_id) if self.applicant_id else None,
            "payload": self.payload,
        }


class AuditTrail:
    def __init__(self, session: Optional[Session] = None) -> None:
        self._store: list[AuditEvent] = []
        self._session = session

    def record(self, event: AuditEvent) -> None:
        self._store.append(event)
        self._persist(event)

    def get_case_history(self, case_id: UUID) -> list[AuditEvent]:
        if self._session is not None:
            from src.infra.repositories import AuditEventRepository

            return AuditEventRepository(self._session).list_for_case(case_id)
        return [e for e in self._store if e.case_id == case_id]

    def _persist(self, event: AuditEvent) -> None:
        if self._session is None:
            return
        from src.infra.repositories import AuditEventRepository

        AuditEventRepository(self._session).add(event)


_audit_trail = AuditTrail()


def get_audit_trail() -> AuditTrail:
    return _audit_trail


def record_event(
    event_type: AuditEventType,
    case_id: UUID,
    actor: str,
    payload: dict | None = None,
    applicant_id: UUID | None = None,
) -> None:
    get_audit_trail().record(AuditEvent(
        event_type=event_type,
        case_id=case_id,
        actor=actor,
        applicant_id=applicant_id,
        payload=payload or {},
    ))
