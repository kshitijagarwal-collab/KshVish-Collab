from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.domain.kyc_case import CaseStatus
from src.core.workflow.state_machine import InvalidTransitionError
from src.infra.audit import AuditEvent, AuditEventType, AuditTrail
from src.infra.db import get_session
from src.infra.repositories import CaseRepository

from .cases import _case_to_response
from .schemas import ApproveRequest, CaseResponse, RejectRequest

router = APIRouter(prefix="/cases", tags=["Workflow"])


@router.post("/{case_id}/approve", response_model=CaseResponse)
def approve_case(
    case_id: UUID,
    body: ApproveRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CaseResponse:
    repo = CaseRepository(session)
    case = repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case.reviewer_id = body.reviewer_id
    try:
        case.transition(CaseStatus.APPROVED, actor=body.reviewer_id, reason=body.notes or "")
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    repo.update(case)
    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.CASE_APPROVED,
            case_id=case_id,
            actor=body.reviewer_id,
            payload={"notes": body.notes or ""},
        )
    )
    session.commit()
    return _case_to_response(case)


@router.post("/{case_id}/reject", response_model=CaseResponse)
def reject_case(
    case_id: UUID,
    body: RejectRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CaseResponse:
    repo = CaseRepository(session)
    case = repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case.reviewer_id = body.reviewer_id
    case.rejection_reason = body.reason
    try:
        case.transition(CaseStatus.REJECTED, actor=body.reviewer_id, reason=body.reason)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    repo.update(case)
    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.CASE_REJECTED,
            case_id=case_id,
            actor=body.reviewer_id,
            payload={"reason": body.reason},
        )
    )
    session.commit()
    return _case_to_response(case)
