from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_loads() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "KYC Onboarding Platform"


def test_routes_mounted_under_api_prefix() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/cases" in paths
    assert "/api/cases/{case_id}" in paths
    assert "/api/cases/{case_id}/documents" in paths
    assert "/api/cases/{case_id}/screen" in paths
    assert "/api/cases/{case_id}/approve" in paths
    assert "/api/cases/{case_id}/audit" in paths
    assert "/health" in paths
