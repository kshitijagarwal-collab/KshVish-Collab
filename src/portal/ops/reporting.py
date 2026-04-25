from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.domain.kyc_case import CaseStatus, RiskTier
from src.infra.orm import KYCCaseORM

from .database import get_session

router = APIRouter(prefix="/ops/cases", tags=["ops"])

_CSV_COLUMNS = (
    "case_id",
    "case_type",
    "country_code",
    "fund_id",
    "status",
    "risk_tier",
    "reviewer_id",
    "created_at",
    "updated_at",
    "expiry_date",
    "rejection_reason",
)


def _serialize(orm: KYCCaseORM) -> dict[str, str]:
    return {
        "case_id": orm.id,
        "case_type": orm.case_type.value,
        "country_code": orm.country_code,
        "fund_id": orm.fund_id,
        "status": orm.status.value,
        "risk_tier": orm.risk_tier.value if orm.risk_tier else "",
        "reviewer_id": orm.reviewer_id or "",
        "created_at": orm.created_at.isoformat(),
        "updated_at": orm.updated_at.isoformat(),
        "expiry_date": orm.expiry_date.isoformat() if orm.expiry_date else "",
        "rejection_reason": orm.rejection_reason or "",
    }


def _stream_csv(rows: list[KYCCaseORM]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS)
    writer.writeheader()
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate()
    for row in rows:
        writer.writerow(_serialize(row))
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()


@router.get("/export")
def export_cases_csv(
    session: Annotated[Session, Depends(get_session)],
    status: Annotated[Optional[CaseStatus], Query()] = None,
    country: Annotated[Optional[str], Query(max_length=8)] = None,
    risk_tier: Annotated[Optional[RiskTier], Query()] = None,
    fund_id: Annotated[Optional[str], Query(max_length=64)] = None,
) -> StreamingResponse:
    stmt = select(KYCCaseORM)
    if status is not None:
        stmt = stmt.where(KYCCaseORM.status == status)
    if country is not None:
        stmt = stmt.where(KYCCaseORM.country_code == country.upper())
    if risk_tier is not None:
        stmt = stmt.where(KYCCaseORM.risk_tier == risk_tier)
    if fund_id is not None:
        stmt = stmt.where(KYCCaseORM.fund_id == fund_id)
    stmt = stmt.order_by(KYCCaseORM.created_at)

    rows = list(session.execute(stmt).scalars().all())

    return StreamingResponse(
        _stream_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kyc-cases.csv"},
    )
