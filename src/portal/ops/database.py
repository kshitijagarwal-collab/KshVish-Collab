from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _make_engine() -> Engine:
    url = os.environ.get("DATABASE_URL", "sqlite:///./kyc.db")
    return create_engine(url)


engine: Engine = _make_engine()
_SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
