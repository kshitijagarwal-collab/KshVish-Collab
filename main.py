from __future__ import annotations

from fastapi import FastAPI

from src.api.rest import (
    audit_router,
    cases_router,
    documents_router,
    screening_router,
    workflow_router,
)
from src.portal.applicant.router import router as applicant_router
from src.portal.ops import (
    assignment_router,
    case_queue_router,
    reporting_router,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="KYC Onboarding Platform",
        version="0.1.0",
        description="Global KYC onboarding for fund management companies.",
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(cases_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(screening_router, prefix="/api")
    app.include_router(workflow_router, prefix="/api")
    app.include_router(audit_router, prefix="/api")

    app.include_router(case_queue_router, prefix="/api")
    app.include_router(assignment_router, prefix="/api")
    app.include_router(reporting_router, prefix="/api")

    app.include_router(applicant_router, prefix="/api")

    return app


app = create_app()
