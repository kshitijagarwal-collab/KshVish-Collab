from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.api.auth import jwt as jwt_module
from src.api.auth.jwt import (
    AuthSettings,
    Principal,
    create_access_token,
    decode_token,
    get_current_principal,
)


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        secret="test-secret-do-not-use-in-prod",
        algorithm="HS256",
        access_token_ttl_minutes=15,
    )


@pytest.fixture(autouse=True)
def _override_module_settings(monkeypatch: pytest.MonkeyPatch, settings: AuthSettings) -> None:
    monkeypatch.setattr(jwt_module, "_settings", settings)


def test_create_and_decode_round_trip(settings: AuthSettings) -> None:
    token = create_access_token("user-123", roles=["REVIEWER"], settings=settings)
    principal = decode_token(token, settings=settings)
    assert principal.subject == "user-123"
    assert principal.roles == ["REVIEWER"]
    assert principal.expires_at > datetime.now(timezone.utc)


def test_create_token_without_roles_yields_empty_list(settings: AuthSettings) -> None:
    token = create_access_token("user-123", settings=settings)
    principal = decode_token(token, settings=settings)
    assert principal.roles == []


def test_decode_expired_token_raises_401(settings: AuthSettings) -> None:
    expired_payload = {
        "sub": "user-123",
        "roles": ["REVIEWER"],
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jose_jwt.encode(
        expired_payload, settings.secret, algorithm=settings.algorithm
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(expired_token, settings=settings)
    assert exc.value.status_code == 401


def test_decode_bad_signature_raises_401(settings: AuthSettings) -> None:
    token = create_access_token("user-123", settings=settings)
    other_settings = AuthSettings(secret="another-secret", algorithm=settings.algorithm)
    with pytest.raises(HTTPException) as exc:
        decode_token(token, settings=other_settings)
    assert exc.value.status_code == 401


def test_decode_malformed_token_raises_401(settings: AuthSettings) -> None:
    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-real-jwt", settings=settings)
    assert exc.value.status_code == 401


def test_decode_token_without_subject_raises_401(settings: AuthSettings) -> None:
    payload = {
        "roles": ["REVIEWER"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jose_jwt.encode(payload, settings.secret, algorithm=settings.algorithm)
    with pytest.raises(HTTPException) as exc:
        decode_token(token, settings=settings)
    assert exc.value.status_code == 401


def test_protected_route_without_header_returns_401(settings: AuthSettings) -> None:
    app = FastAPI()

    @app.get("/me")
    def me(principal: Principal = Depends(get_current_principal)) -> dict:
        return {"subject": principal.subject, "roles": principal.roles}

    client = TestClient(app)
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").lower().startswith("bearer")


def test_protected_route_with_valid_token_succeeds(settings: AuthSettings) -> None:
    app = FastAPI()

    @app.get("/me")
    def me(principal: Principal = Depends(get_current_principal)) -> dict:
        return {"subject": principal.subject, "roles": principal.roles}

    client = TestClient(app)
    token = create_access_token(
        "alice", roles=["REVIEWER", "ADMIN"], settings=settings
    )
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body == {"subject": "alice", "roles": ["REVIEWER", "ADMIN"]}


def test_protected_route_with_invalid_token_returns_401(settings: AuthSettings) -> None:
    app = FastAPI()

    @app.get("/me")
    def me(principal: Principal = Depends(get_current_principal)) -> dict:
        return {"subject": principal.subject}

    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401
