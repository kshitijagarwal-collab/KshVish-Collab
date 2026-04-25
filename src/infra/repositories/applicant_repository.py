from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.core.domain.applicant import CorporateApplicant, IndividualApplicant
from src.infra.orm import CorporateApplicantORM, IndividualApplicantORM


class IndividualApplicantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, applicant: IndividualApplicant) -> None:
        self._session.add(IndividualApplicantORM.from_domain(applicant))

    def get(self, applicant_id: UUID) -> Optional[IndividualApplicant]:
        row = self._session.get(IndividualApplicantORM, str(applicant_id))
        return row.to_domain() if row else None


class CorporateApplicantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, applicant: CorporateApplicant) -> None:
        self._session.add(CorporateApplicantORM.from_domain(applicant))

    def get(self, applicant_id: UUID) -> Optional[CorporateApplicant]:
        row = self._session.get(CorporateApplicantORM, str(applicant_id))
        return row.to_domain() if row else None
