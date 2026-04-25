from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase, RiskTier
from src.infra.orm import Base
from src.infra.repositories import CaseRepository
from src.portal.ops.case_queue import router
from src.portal.ops.database import get_session
from src.portal.ops.security import require_ops_role


@pytest.fixture
def engine() -> Engine:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def app(engine: Engine) -> FastAPI:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    application = FastAPI()
    application.include_router(router)

    def _override_session() -> Iterator[Session]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_session] = _override_session
    application.dependency_overrides[require_ops_role] = lambda: None
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _case(
    status: CaseStatus = CaseStatus.INITIATED,
    country: str = "GB",
    risk: Optional[RiskTier] = None,
    fund_id: str = "FUND-001",
    case_type: CaseType = CaseType.INDIVIDUAL,
    minute: int = 0,
) -> KYCCase:
    return KYCCase(
        case_type=case_type,
        country_code=country,
        fund_id=fund_id,
        status=status,
        risk_tier=risk,
        created_at=datetime(2026, 4, 25, 12, minute, 0),
        updated_at=datetime(2026, 4, 25, 12, minute, 0),
    )


def _seed(engine: Engine, *cases: KYCCase) -> None:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        repo = CaseRepository(session)
        for case in cases:
            repo.add(case)
        session.commit()


def test_list_cases_no_filter_returns_all(client: TestClient, engine: Engine) -> None:
    _seed(engine, _case(country="GB"), _case(country="US"))
    response = client.get("/ops/cases")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_cases_returns_empty_when_no_data(client: TestClient) -> None:
    response = client.get("/ops/cases")
    assert response.status_code == 200
    assert response.json() == []


def test_filter_by_status(client: TestClient, engine: Engine) -> None:
    _seed(
        engine,
        _case(status=CaseStatus.IN_REVIEW),
        _case(status=CaseStatus.APPROVED),
        _case(status=CaseStatus.IN_REVIEW),
    )
    response = client.get("/ops/cases?status=IN_REVIEW")
    body = response.json()
    assert len(body) == 2
    assert all(c["status"] == "IN_REVIEW" for c in body)


def test_filter_by_country(client: TestClient, engine: Engine) -> None:
    _seed(engine, _case(country="GB"), _case(country="US"), _case(country="GB"))
    response = client.get("/ops/cases?country=GB")
    body = response.json()
    assert len(body) == 2
    assert all(c["country_code"] == "GB" for c in body)


def test_filter_by_country_is_case_insensitive(
    client: TestClient, engine: Engine
) -> None:
    _seed(engine, _case(country="GB"))
    response = client.get("/ops/cases?country=gb")
    assert len(response.json()) == 1


def test_filter_by_risk_tier(client: TestClient, engine: Engine) -> None:
    _seed(
        engine,
        _case(risk=RiskTier.HIGH),
        _case(risk=RiskTier.LOW),
        _case(risk=RiskTier.HIGH),
    )
    response = client.get("/ops/cases?risk_tier=HIGH")
    body = response.json()
    assert len(body) == 2
    assert all(c["risk_tier"] == "HIGH" for c in body)


def test_filter_by_fund_id(client: TestClient, engine: Engine) -> None:
    _seed(engine, _case(fund_id="FUND-A"), _case(fund_id="FUND-B"))
    response = client.get("/ops/cases?fund_id=FUND-A")
    body = response.json()
    assert len(body) == 1
    assert body[0]["fund_id"] == "FUND-A"


def test_combined_filters(client: TestClient, engine: Engine) -> None:
    _seed(
        engine,
        _case(status=CaseStatus.IN_REVIEW, country="GB", risk=RiskTier.HIGH),
        _case(status=CaseStatus.IN_REVIEW, country="US", risk=RiskTier.HIGH),
        _case(status=CaseStatus.APPROVED, country="GB", risk=RiskTier.HIGH),
        _case(status=CaseStatus.IN_REVIEW, country="GB", risk=RiskTier.LOW),
    )
    response = client.get("/ops/cases?status=IN_REVIEW&country=GB&risk_tier=HIGH")
    body = response.json()
    assert len(body) == 1
    assert body[0]["country_code"] == "GB"
    assert body[0]["status"] == "IN_REVIEW"
    assert body[0]["risk_tier"] == "HIGH"


def test_pagination_limit_and_offset(client: TestClient, engine: Engine) -> None:
    _seed(engine, *(_case(minute=i) for i in range(10)))

    page1 = client.get("/ops/cases?limit=4").json()
    assert len(page1) == 4

    page2 = client.get("/ops/cases?limit=4&offset=4").json()
    assert len(page2) == 4

    page3 = client.get("/ops/cases?limit=4&offset=8").json()
    assert len(page3) == 2


def test_results_ordered_by_created_at_desc(
    client: TestClient, engine: Engine
) -> None:
    _seed(
        engine,
        _case(country="A1", minute=1),
        _case(country="A2", minute=5),
        _case(country="A3", minute=3),
    )
    body = client.get("/ops/cases").json()
    countries = [c["country_code"] for c in body]
    assert countries == ["A2", "A3", "A1"]


def test_invalid_status_returns_422(client: TestClient) -> None:
    response = client.get("/ops/cases?status=NOT_A_STATUS")
    assert response.status_code == 422


def test_limit_above_max_returns_422(client: TestClient) -> None:
    response = client.get("/ops/cases?limit=1000")
    assert response.status_code == 422
