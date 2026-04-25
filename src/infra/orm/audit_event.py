from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, JSON, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.audit import AuditEvent, AuditEventType

from .base import Base


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    applicant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    @classmethod
    def from_domain(cls, event: AuditEvent) -> "AuditEventORM":
        return cls(
            id=str(event.id),
            event_type=event.event_type,
            case_id=str(event.case_id),
            actor=event.actor,
            occurred_at=event.occurred_at,
            applicant_id=str(event.applicant_id) if event.applicant_id else None,
            payload=dict(event.payload),
            ip_address=event.ip_address,
            session_id=event.session_id,
        )

    def to_domain(self) -> AuditEvent:
        return AuditEvent(
            id=UUID(self.id),
            event_type=self.event_type,
            case_id=UUID(self.case_id),
            actor=self.actor,
            occurred_at=self.occurred_at,
            applicant_id=UUID(self.applicant_id) if self.applicant_id else None,
            payload=dict(self.payload or {}),
            ip_address=self.ip_address,
            session_id=self.session_id,
        )
