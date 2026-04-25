from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _make_session_factory() -> sessionmaker[Session]:
    url = os.environ.get("DATABASE_URL", "sqlite:///./kyc.db")
    engine = create_engine(url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


_SessionLocal = _make_session_factory()


def get_session() -> Iterator[Session]:
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
