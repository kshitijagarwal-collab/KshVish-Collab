from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt  # type: ignore[import-untyped]
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KYC_AUTH_", case_sensitive=False)

    secret: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60


class Principal(BaseModel):
    subject: str
    roles: list[str] = Field(default_factory=list)
    expires_at: datetime


_settings: Optional[AuthSettings] = None


def get_settings() -> AuthSettings:
    global _settings
    if _settings is None:
        _settings = AuthSettings()
    return _settings


def create_access_token(
    subject: str,
    roles: Optional[list[str]] = None,
    *,
    settings: Optional[AuthSettings] = None,
) -> str:
    s = settings or get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_ttl_minutes)
    payload: dict[str, object] = {
        "sub": subject,
        "roles": roles or [],
        "exp": expires_at,
    }
    return jwt.encode(payload, s.secret, algorithm=s.algorithm)


def decode_token(token: str, *, settings: Optional[AuthSettings] = None) -> Principal:
    s = settings or get_settings()
    try:
        payload = jwt.decode(token, s.secret, algorithms=[s.algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = payload.get("sub")
    if not subject or not isinstance(subject, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_roles = payload.get("roles", [])
    roles = [str(r) for r in raw_roles] if isinstance(raw_roles, list) else []

    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        expires_at = datetime.fromtimestamp(float(exp), tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc)

    return Principal(subject=subject, roles=roles, expires_at=expires_at)


_bearer = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)
