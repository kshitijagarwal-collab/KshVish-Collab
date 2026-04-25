from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_screen_unknown_case_returns_404(client: TestClient) -> None:
    response = client.post(f"/cases/{uuid4()}/screen")
    assert response.status_code == 404


def test_screen_corporate_returns_422(
    client: TestClient, sample_corporate_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_corporate_payload).json()["case_id"]
    response = client.post(f"/cases/{case_id}/screen")
    assert response.status_code == 422


def test_screen_individual_returns_full_response(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_individual_payload).json()["case_id"]
    client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    )
    response = client.post(f"/cases/{case_id}/screen")
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == case_id
    assert "identity_passed" in body
    assert "sanctions_clear" in body
    assert "is_pep" in body
    assert "risk_tier" in body


def test_screening_records_audit_events(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_individual_payload).json()["case_id"]
    client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    )
    client.post(f"/cases/{case_id}/screen")

    events = client.get(f"/cases/{case_id}/audit").json()
    types = {e["event_type"] for e in events}
    assert "SANCTIONS_SCREENED" in types
    assert "PEP_SCREENED" in types
    assert "RISK_SCORED" in types
