from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.rest import (
    audit_router,
    cases_router,
    documents_router,
    screening_router,
    workflow_router,
)
from src.infra.db import get_session
from src.infra.orm import Base


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
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def app(session_factory: sessionmaker[Session]) -> FastAPI:
    application = FastAPI()
    application.include_router(cases_router)
    application.include_router(documents_router)
    application.include_router(screening_router)
    application.include_router(workflow_router)
    application.include_router(audit_router)

    def _override_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_session] = _override_session
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_individual_payload() -> dict:
    return {
        "case_type": "INDIVIDUAL",
        "country_code": "GB",
        "fund_id": "FUND-001",
        "individual": {
            "first_name": "Alice",
            "last_name": "Smith",
            "date_of_birth": "1990-05-01",
            "nationality": "GB",
            "country_of_residence": "GB",
            "email": "alice@example.com",
        },
    }


@pytest.fixture
def sample_corporate_payload() -> dict:
    return {
        "case_type": "CORPORATE",
        "country_code": "GB",
        "fund_id": "FUND-002",
        "corporate": {
            "legal_name": "Acme Ltd",
            "registration_number": "12345",
            "country_of_incorporation": "GB",
            "registered_address": {
                "line1": "1 Cheapside",
                "city": "London",
                "country_code": "GB",
                "postal_code": "EC2V 6DN",
            },
        },
    }
