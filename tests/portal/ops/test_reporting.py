from __future__ import annotations

import csv
import io
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
from src.portal.ops.database import get_session
from src.portal.ops.reporting import router
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
    reviewer_id: Optional[str] = None,
) -> KYCCase:
    return KYCCase(
        case_type=case_type,
        country_code=country,
        fund_id=fund_id,
        status=status,
        risk_tier=risk,
        reviewer_id=reviewer_id,
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


def _parse_csv(body: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(body)))


def test_export_returns_csv_with_header(client: TestClient, engine: Engine) -> None:
    _seed(engine, _case())
    response = client.get("/ops/cases/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "kyc-cases.csv" in response.headers["content-disposition"]

    rows = _parse_csv(response.text)
    assert len(rows) == 1
    assert "case_id" in rows[0]
    assert "country_code" in rows[0]


def test_export_empty_returns_header_only(client: TestClient) -> None:
    response = client.get("/ops/cases/export")
    rows = _parse_csv(response.text)
    assert rows == []


def test_export_filter_by_status(client: TestClient, engine: Engine) -> None:
    _seed(
        engine,
        _case(status=CaseStatus.IN_REVIEW),
        _case(status=CaseStatus.APPROVED),
    )
    response = client.get("/ops/cases/export?status=IN_REVIEW")
    rows = _parse_csv(response.text)
    assert len(rows) == 1
    assert rows[0]["status"] == "IN_REVIEW"


def test_export_filter_by_country_case_insensitive(
    client: TestClient, engine: Engine
) -> None:
    _seed(engine, _case(country="GB"), _case(country="US"))
    response = client.get("/ops/cases/export?country=gb")
    rows = _parse_csv(response.text)
    assert len(rows) == 1
    assert rows[0]["country_code"] == "GB"


def test_export_combines_filters(client: TestClient, engine: Engine) -> None:
    _seed(
        engine,
        _case(status=CaseStatus.IN_REVIEW, country="GB", risk=RiskTier.HIGH),
        _case(status=CaseStatus.IN_REVIEW, country="US", risk=RiskTier.HIGH),
        _case(status=CaseStatus.APPROVED, country="GB", risk=RiskTier.HIGH),
    )
    response = client.get(
        "/ops/cases/export?status=IN_REVIEW&country=GB&risk_tier=HIGH"
    )
    rows = _parse_csv(response.text)
    assert len(rows) == 1


def test_export_renders_optional_fields(client: TestClient, engine: Engine) -> None:
    _seed(
        engine,
        _case(risk=RiskTier.HIGH, reviewer_id="reviewer-1"),
        _case(),
    )
    response = client.get("/ops/cases/export")
    rows = _parse_csv(response.text)
    risky = next(r for r in rows if r["risk_tier"] == "HIGH")
    assert risky["reviewer_id"] == "reviewer-1"
    blank = next(r for r in rows if r["risk_tier"] == "")
    assert blank["reviewer_id"] == ""


def test_export_columns_are_stable(client: TestClient, engine: Engine) -> None:
    """Compliance reports have fixed schemas; field order matters for downstream tooling."""
    _seed(engine, _case())
    response = client.get("/ops/cases/export")
    header_row = response.text.splitlines()[0]
    assert header_row == (
        "case_id,case_type,country_code,fund_id,status,risk_tier,reviewer_id,"
        "created_at,updated_at,expiry_date,rejection_reason"
    )
