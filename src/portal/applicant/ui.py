from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/portal/applicant", tags=["Applicant Portal UI"])

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def portal_home(request: Request) -> HTMLResponse:
    return _TEMPLATES.TemplateResponse(request, "portal.html", {})
