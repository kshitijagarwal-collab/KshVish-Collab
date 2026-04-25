from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.domain.kyc_case import CaseStatus, CaseType, RiskTier
from src.infra.orm import KYCCaseORM

from .database import get_session
from .security import require_ops_role

router = APIRouter(
    prefix="/ops/cases",
    tags=["ops"],
    dependencies=[Depends(require_ops_role)],
)


class CaseSummary(BaseModel):
    id: str
    case_type: CaseType
    country_code: str
    fund_id: str
    status: CaseStatus
    risk_tier: Optional[RiskTier]
    reviewer_id: Optional[str]


@router.get("", response_model=list[CaseSummary])
def list_cases(
    session: Annotated[Session, Depends(get_session)],
    status: Annotated[Optional[CaseStatus], Query()] = None,
    country: Annotated[Optional[str], Query(max_length=8)] = None,
    risk_tier: Annotated[Optional[RiskTier], Query()] = None,
    fund_id: Annotated[Optional[str], Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CaseSummary]:
    stmt = select(KYCCaseORM)
    if status is not None:
        stmt = stmt.where(KYCCaseORM.status == status)
    if country is not None:
        stmt = stmt.where(KYCCaseORM.country_code == country.upper())
    if risk_tier is not None:
        stmt = stmt.where(KYCCaseORM.risk_tier == risk_tier)
    if fund_id is not None:
        stmt = stmt.where(KYCCaseORM.fund_id == fund_id)
    stmt = stmt.order_by(KYCCaseORM.created_at.desc()).limit(limit).offset(offset)

    rows = session.execute(stmt).scalars().all()
    return [
        CaseSummary(
            id=r.id,
            case_type=r.case_type,
            country_code=r.country_code,
            fund_id=r.fund_id,
            status=r.status,
            risk_tier=r.risk_tier,
            reviewer_id=r.reviewer_id,
        )
        for r in rows
    ]
