from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.auth.jwt import Principal, get_current_principal
from src.api.auth.rbac import Role, require_role


def _principal(*roles: str) -> Principal:
    return Principal(
        subject="user-1",
        roles=list(roles),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )


def _make_app(dep, principal: Principal) -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    def protected(p: Principal = Depends(dep)) -> dict:
        return {"subject": p.subject, "roles": p.roles}

    app.dependency_overrides[get_current_principal] = lambda: principal
    return TestClient(app)


def test_require_role_accepts_matching_role() -> None:
    client = _make_app(require_role(Role.ADMIN), _principal("ADMIN"))
    response = client.get("/protected")
    assert response.status_code == 200
    assert response.json() == {"subject": "user-1", "roles": ["ADMIN"]}


def test_require_role_accepts_when_user_has_one_of_multiple_allowed() -> None:
    client = _make_app(
        require_role(Role.REVIEWER, Role.ADMIN),
        _principal("REVIEWER"),
    )
    response = client.get("/protected")
    assert response.status_code == 200


def test_require_role_rejects_user_without_required_role() -> None:
    client = _make_app(require_role(Role.ADMIN), _principal("APPLICANT"))
    response = client.get("/protected")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_require_role_rejects_user_with_no_roles() -> None:
    client = _make_app(require_role(Role.REVIEWER), _principal())
    response = client.get("/protected")
    assert response.status_code == 403


def test_require_role_with_no_args_raises_value_error() -> None:
    with pytest.raises(ValueError):
        require_role()


def test_role_enum_values() -> None:
    assert Role.REVIEWER.value == "REVIEWER"
    assert Role.ADMIN.value == "ADMIN"
    assert Role.APPLICANT.value == "APPLICANT"


def test_require_role_returns_principal_unchanged() -> None:
    """The dependency returns the same Principal so handlers can read claims."""
    app = FastAPI()
    captured: list[Principal] = []

    @app.get("/protected")
    def protected(p: Principal = Depends(require_role(Role.ADMIN))) -> dict:
        captured.append(p)
        return {"ok": True}

    expected = _principal("ADMIN", "REVIEWER")
    app.dependency_overrides[get_current_principal] = lambda: expected
    client = TestClient(app)

    response = client.get("/protected")
    assert response.status_code == 200
    assert captured[0] is expected
