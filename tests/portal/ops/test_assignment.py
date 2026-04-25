from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase
from src.infra.orm import Base
from src.infra.repositories import CaseRepository
from src.portal.ops.assignment import router
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


def _seed_case(engine: Engine) -> KYCCase:
    case = KYCCase(
        case_type=CaseType.INDIVIDUAL,
        country_code="GB",
        fund_id="FUND-001",
        status=CaseStatus.IN_REVIEW,
        created_at=datetime(2026, 4, 25, 12, 0, 0),
        updated_at=datetime(2026, 4, 25, 12, 0, 0),
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        CaseRepository(session).add(case)
        session.commit()
    return case


def test_assign_reviewer_succeeds(client: TestClient, engine: Engine) -> None:
    case = _seed_case(engine)
    response = client.post(
        f"/ops/cases/{case.id}/assign",
        json={"reviewer_id": "reviewer-7"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "case_id": str(case.id),
        "reviewer_id": "reviewer-7",
    }


def test_assignment_persists_across_sessions(
    client: TestClient, engine: Engine
) -> None:
    case = _seed_case(engine)
    client.post(
        f"/ops/cases/{case.id}/assign",
        json={"reviewer_id": "reviewer-7"},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        refreshed = CaseRepository(session).get(case.id)
    assert refreshed is not None
    assert refreshed.reviewer_id == "reviewer-7"


def test_assign_reviewer_unknown_case_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/ops/cases/{uuid4()}/assign",
        json={"reviewer_id": "reviewer-7"},
    )
    assert response.status_code == 404


def test_assign_reviewer_blank_reviewer_id_returns_422(
    client: TestClient, engine: Engine
) -> None:
    case = _seed_case(engine)
    response = client.post(
        f"/ops/cases/{case.id}/assign",
        json={"reviewer_id": ""},
    )
    assert response.status_code == 422


def test_assign_reviewer_overwrites_existing(
    client: TestClient, engine: Engine
) -> None:
    case = _seed_case(engine)
    client.post(
        f"/ops/cases/{case.id}/assign",
        json={"reviewer_id": "reviewer-7"},
    )
    response = client.post(
        f"/ops/cases/{case.id}/assign",
        json={"reviewer_id": "reviewer-9"},
    )
    assert response.status_code == 200
    assert response.json()["reviewer_id"] == "reviewer-9"

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        refreshed = CaseRepository(session).get(case.id)
    assert refreshed is not None
    assert refreshed.reviewer_id == "reviewer-9"


def test_invalid_uuid_returns_422(client: TestClient) -> None:
    response = client.post(
        "/ops/cases/not-a-uuid/assign", json={"reviewer_id": "reviewer-7"}
    )
    assert response.status_code == 422
