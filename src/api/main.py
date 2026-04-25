from __future__ import annotations

from fastapi import FastAPI

from src.api.rest import audit, cases, documents, screening

app = FastAPI(
    title="KYC Onboarding Platform",
    description="Global KYC API — Individual, Corporate, and Institutional onboarding.",
    version="0.1.0",
)

app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(screening.router)
app.include_router(audit.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
