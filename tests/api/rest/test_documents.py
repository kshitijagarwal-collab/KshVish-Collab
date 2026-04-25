from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_case(client: TestClient, payload: dict) -> str:
    return client.post("/cases", json=payload).json()["case_id"]


def test_upload_document_transitions_case_to_documents_pending(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = _create_case(client, sample_individual_payload)

    response = client.post(
        f"/cases/{case_id}/documents",
        json={
            "doc_type": "PASSPORT",
            "file_name": "passport.pdf",
            "storage_ref": "s3://bucket/passport",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["doc_type"] == "PASSPORT"
    assert body["status"] == "UPLOADED"

    refreshed = client.get(f"/cases/{case_id}").json()
    assert refreshed["status"] == "DOCUMENTS_PENDING"


def test_upload_document_unknown_case_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/cases/{uuid4()}/documents",
        json={"doc_type": "PASSPORT", "file_name": "x.pdf", "storage_ref": "s3://x"},
    )
    assert response.status_code == 404


def test_list_documents_returns_uploaded(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = _create_case(client, sample_individual_payload)
    client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    )
    client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PROOF_OF_ADDRESS", "file_name": "a.pdf", "storage_ref": "s3://a"},
    )

    response = client.get(f"/cases/{case_id}/documents")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_verify_document(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = _create_case(client, sample_individual_payload)
    doc = client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    ).json()

    response = client.patch(
        f"/cases/{case_id}/documents/{doc['document_id']}/verify",
        json={"reviewer_id": "reviewer-1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "VERIFIED"


def test_reject_document(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = _create_case(client, sample_individual_payload)
    doc = client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    ).json()

    response = client.patch(
        f"/cases/{case_id}/documents/{doc['document_id']}/reject",
        json={"reason": "Blurry image"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"


def test_verify_unknown_document_returns_404(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = _create_case(client, sample_individual_payload)
    response = client.patch(
        f"/cases/{case_id}/documents/{uuid4()}/verify",
        json={"reviewer_id": "reviewer-1"},
    )
    assert response.status_code == 404
