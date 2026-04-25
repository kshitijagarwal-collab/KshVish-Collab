from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.infra.audit import AuditTrail
from src.infra.db import get_session
from src.infra.repositories import CaseRepository

from .schemas import AuditEventOut

router = APIRouter(prefix="/cases", tags=["Audit"])


@router.get("/{case_id}/audit", response_model=list[AuditEventOut])
def get_case_audit_trail(
    case_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[AuditEventOut]:
    if CaseRepository(session).get(case_id) is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    events = AuditTrail(session=session).get_case_history(case_id)
    return [
        AuditEventOut(
            event_id=e.id,
            case_id=e.case_id,
            event_type=e.event_type.value,
            actor=e.actor,
            occurred_at=e.occurred_at,
            payload=e.payload,
        )
        for e in events
    ]
