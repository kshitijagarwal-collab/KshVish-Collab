from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth import jwt as jwt_module
from src.api.auth.jwt import AuthSettings, create_access_token
from src.infra.orm import Base
from src.portal.ops.app import create_app
from src.portal.ops.database import get_session


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        secret="test-secret-do-not-use-in-prod",
        algorithm="HS256",
        access_token_ttl_minutes=15,
    )


@pytest.fixture(autouse=True)
def _override_jwt_settings(monkeypatch: pytest.MonkeyPatch, settings: AuthSettings) -> None:
    monkeypatch.setattr(jwt_module, "_settings", settings)


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
def client(engine: Engine) -> Iterator[TestClient]:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def _override_session() -> Iterator[Session]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _bearer(roles: list[str], settings: AuthSettings) -> dict[str, str]:
    token = create_access_token("ops-user", roles=roles, settings=settings)
    return {"Authorization": f"Bearer {token}"}


def test_routes_registered() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/ops/cases" in paths
    assert "/ops/cases/{case_id}/assign" in paths
    assert "/ops/cases/export" in paths


def test_list_cases_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/ops/cases")
    assert response.status_code == 401


def test_list_cases_with_applicant_role_returns_403(
    client: TestClient, settings: AuthSettings
) -> None:
    response = client.get("/ops/cases", headers=_bearer(["APPLICANT"], settings))
    assert response.status_code == 403


def test_list_cases_with_reviewer_role_returns_200(
    client: TestClient, settings: AuthSettings
) -> None:
    response = client.get("/ops/cases", headers=_bearer(["REVIEWER"], settings))
    assert response.status_code == 200
    assert response.json() == []


def test_list_cases_with_admin_role_returns_200(
    client: TestClient, settings: AuthSettings
) -> None:
    response = client.get("/ops/cases", headers=_bearer(["ADMIN"], settings))
    assert response.status_code == 200


def test_export_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/ops/cases/export")
    assert response.status_code == 401


def test_assign_without_token_returns_401(client: TestClient) -> None:
    response = client.post(
        "/ops/cases/00000000-0000-0000-0000-000000000000/assign",
        json={"reviewer_id": "rev-1"},
    )
    assert response.status_code == 401


def test_create_app_initialises_schema(engine: Engine) -> None:
    inspector_tables = Base.metadata.tables.keys()
    assert "kyc_cases" in inspector_tables
    assert "documents" in inspector_tables
