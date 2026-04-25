from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.domain.kyc_case import CaseStatus, KYCCase
from src.infra.orm import KYCCaseORM

from .errors import CaseNotFoundError


class CaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, case: KYCCase) -> None:
        self._session.add(KYCCaseORM.from_domain(case))

    def get(self, case_id: UUID) -> Optional[KYCCase]:
        row = self._session.get(KYCCaseORM, str(case_id))
        return row.to_domain() if row else None

    def list_by_status(self, status: CaseStatus) -> list[KYCCase]:
        stmt = select(KYCCaseORM).where(KYCCaseORM.status == status)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def list_by_country(self, country_code: str) -> list[KYCCase]:
        stmt = select(KYCCaseORM).where(KYCCaseORM.country_code == country_code)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def update(self, case: KYCCase) -> KYCCase:
        if self._session.get(KYCCaseORM, str(case.id)) is None:
            raise CaseNotFoundError(case.id)
        self._session.merge(KYCCaseORM.from_domain(case))
        return case
