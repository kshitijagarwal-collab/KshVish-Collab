from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_portal_html_loads() -> None:
    client = TestClient(app)
    response = client.get("/portal/applicant/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "KYC Applicant Portal" in response.text


def test_portal_html_loads_without_trailing_slash() -> None:
    client = TestClient(app)
    response = client.get("/portal/applicant", follow_redirects=False)
    assert response.status_code == 200


def test_portal_not_in_openapi_schema() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert "/portal/applicant" not in schema["paths"]
    assert "/portal/applicant/" not in schema["paths"]
