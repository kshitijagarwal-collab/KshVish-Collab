from __future__ import annotations

from fastapi import FastAPI

from src.infra.orm import Base

from .assignment import router as assignment_router
from .case_queue import router as case_queue_router
from .database import engine
from .reporting import router as reporting_router


def create_app() -> FastAPI:
    app = FastAPI(title="KYC Ops Portal")
    Base.metadata.create_all(bind=engine)
    app.include_router(case_queue_router)
    app.include_router(assignment_router)
    app.include_router(reporting_router)
    return app
