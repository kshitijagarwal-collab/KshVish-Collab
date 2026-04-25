from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infra import store

router = APIRouter(prefix="/cases", tags=["Audit"])


class AuditEventResponse(BaseModel):
    event_id: UUID
    case_id: UUID
    event_type: str
    actor: str
    occurred_at: datetime
    payload: dict


@router.get("/{case_id}/audit", response_model=list[AuditEventResponse])
def get_audit_trail(case_id: UUID) -> list[AuditEventResponse]:
    if not store.get_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    events = store.get_audit_events(case_id)
    return [
        AuditEventResponse(
            event_id=e.id,
            case_id=e.case_id,
            event_type=str(e.event_type),
            actor=e.actor,
            occurred_at=e.occurred_at,
            payload=e.payload,
        )
        for e in events
    ]
