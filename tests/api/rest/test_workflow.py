from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.core.domain.kyc_case import CaseStatus
from src.infra.repositories import CaseRepository


def _bring_case_to_in_review(client: TestClient, session_factory: sessionmaker, payload: dict) -> str:
    case_id = client.post("/cases", json=payload).json()["case_id"]
    client.post(
        f"/cases/{case_id}/documents",
        json={"doc_type": "PASSPORT", "file_name": "p.pdf", "storage_ref": "s3://p"},
    )
    # Force-transition to IN_REVIEW via repo (skip screening to keep tests focused on workflow).
    from uuid import UUID

    with session_factory() as session:
        repo = CaseRepository(session)
        case = repo.get(UUID(case_id))
        assert case is not None
        case.transition(CaseStatus.IN_REVIEW, actor="test", reason="setup")
        repo.update(case)
        session.commit()
    return case_id


def test_approve_case_succeeds(
    client: TestClient,
    session_factory: sessionmaker,
    sample_individual_payload: dict,
) -> None:
    case_id = _bring_case_to_in_review(client, session_factory, sample_individual_payload)

    response = client.post(
        f"/cases/{case_id}/approve",
        json={"reviewer_id": "reviewer-1", "notes": "All clear"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["reviewer_id"] == "reviewer-1"


def test_approve_unknown_case_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/cases/{uuid4()}/approve",
        json={"reviewer_id": "reviewer-1"},
    )
    assert response.status_code == 404


def test_approve_from_initiated_returns_409(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_individual_payload).json()["case_id"]
    response = client.post(
        f"/cases/{case_id}/approve",
        json={"reviewer_id": "reviewer-1"},
    )
    assert response.status_code == 409


def test_reject_case_succeeds(
    client: TestClient, sample_individual_payload: dict
) -> None:
    case_id = client.post("/cases", json=sample_individual_payload).json()["case_id"]

    response = client.post(
        f"/cases/{case_id}/reject",
        json={"reviewer_id": "reviewer-1", "reason": "incomplete data"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["rejection_reason"] == "incomplete data"


def test_reject_after_approve_returns_409(
    client: TestClient,
    session_factory: sessionmaker,
    sample_individual_payload: dict,
) -> None:
    case_id = _bring_case_to_in_review(client, session_factory, sample_individual_payload)
    client.post(f"/cases/{case_id}/approve", json={"reviewer_id": "r1"})

    response = client.post(
        f"/cases/{case_id}/reject",
        json={"reviewer_id": "r1", "reason": "changed mind"},
    )
    assert response.status_code == 409
