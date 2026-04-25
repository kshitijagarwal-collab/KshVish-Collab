from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.infra.repositories import CaseNotFoundError, CaseRepository

from .database import get_session

router = APIRouter(prefix="/ops/cases", tags=["ops"])


class AssignReviewerRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=64)


class AssignReviewerResponse(BaseModel):
    case_id: str
    reviewer_id: str


@router.post("/{case_id}/assign", response_model=AssignReviewerResponse)
def assign_reviewer(
    case_id: UUID,
    body: AssignReviewerRequest,
    session: Annotated[Session, Depends(get_session)],
) -> AssignReviewerResponse:
    repo = CaseRepository(session)
    case = repo.get(case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    case.reviewer_id = body.reviewer_id
    try:
        repo.update(case)
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    session.commit()
    return AssignReviewerResponse(case_id=str(case.id), reviewer_id=body.reviewer_id)
