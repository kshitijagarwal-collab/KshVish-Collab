from __future__ import annotations
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kyc.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()


def init_db() -> None:
    from src.infra.orm import models  # noqa: F401 — register models on Base
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    from src.infra.orm import models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
