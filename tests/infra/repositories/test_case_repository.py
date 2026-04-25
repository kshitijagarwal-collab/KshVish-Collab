from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase, RiskTier
from src.infra.orm import Base
from src.infra.repositories import CaseNotFoundError, CaseRepository


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _new_case(
    status: CaseStatus = CaseStatus.INITIATED,
    country: str = "GB",
    case_type: CaseType = CaseType.INDIVIDUAL,
) -> KYCCase:
    return KYCCase(
        case_type=case_type,
        country_code=country,
        fund_id="FUND-001",
        status=status,
        created_at=datetime(2026, 4, 25, 12, 0, 0),
        updated_at=datetime(2026, 4, 25, 12, 0, 0),
    )


def test_add_and_get_round_trip(session: Session) -> None:
    repo = CaseRepository(session)
    case = _new_case()
    repo.add(case)
    session.commit()

    fetched = repo.get(case.id)
    assert fetched == case


def test_get_missing_returns_none(session: Session) -> None:
    repo = CaseRepository(session)
    assert repo.get(uuid4()) is None


def test_list_by_status_filters_correctly(session: Session) -> None:
    repo = CaseRepository(session)
    in_review = _new_case(status=CaseStatus.IN_REVIEW)
    initiated = _new_case(status=CaseStatus.INITIATED)
    approved = _new_case(status=CaseStatus.APPROVED)
    repo.add(in_review)
    repo.add(initiated)
    repo.add(approved)
    session.commit()

    results = repo.list_by_status(CaseStatus.IN_REVIEW)
    assert [c.id for c in results] == [in_review.id]


def test_list_by_country_filters_correctly(session: Session) -> None:
    repo = CaseRepository(session)
    gb_case = _new_case(country="GB")
    us_case = _new_case(country="US")
    repo.add(gb_case)
    repo.add(us_case)
    session.commit()

    results = repo.list_by_country("GB")
    assert [c.id for c in results] == [gb_case.id]


def test_update_persists_changes(session: Session) -> None:
    repo = CaseRepository(session)
    case = _new_case(status=CaseStatus.INITIATED)
    repo.add(case)
    session.commit()

    case.status = CaseStatus.IN_REVIEW
    case.risk_tier = RiskTier.HIGH
    case.reviewer_id = "reviewer-7"
    repo.update(case)
    session.commit()

    refreshed = repo.get(case.id)
    assert refreshed is not None
    assert refreshed.status == CaseStatus.IN_REVIEW
    assert refreshed.risk_tier == RiskTier.HIGH
    assert refreshed.reviewer_id == "reviewer-7"


def test_update_missing_raises(session: Session) -> None:
    repo = CaseRepository(session)
    case = _new_case()
    with pytest.raises(CaseNotFoundError) as exc:
        repo.update(case)
    assert exc.value.case_id == case.id
