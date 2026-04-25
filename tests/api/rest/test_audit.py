from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_audit_trail_includes_case_creation(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_individual_payload).json()["case_id"]

    response = client.get(f"/cases/{case_id}/audit")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "CASE_CREATED"


def test_audit_trail_records_document_upload(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_individual_payload).json()["case_id"]
    client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    )

    events = client.get(f"/cases/{case_id}/audit").json()
    types = {e["event_type"] for e in events}
    assert "CASE_CREATED" in types
    assert "DOCUMENT_UPLOADED" in types


def test_audit_trail_unknown_case_returns_404(client: TestClient) -> None:
    response = client.get(f"/cases/{uuid4()}/audit")
    assert response.status_code == 404
