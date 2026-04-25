from __future__ import annotations

from fastapi import FastAPI

from .router import router as applicant_router


def create_app() -> FastAPI:
    app = FastAPI(title="KYC Applicant Portal")
    app.include_router(applicant_router)
    return app
