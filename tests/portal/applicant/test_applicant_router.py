from __future__ import annotations

from typing import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.auth import jwt as jwt_module
from src.api.auth.jwt import AuthSettings, create_access_token
from src.core.domain.kyc_case import CaseStatus, CaseType
from src.portal.applicant import router as router_module
from src.portal.applicant.app import create_app
from src.portal.applicant.service import InMemoryApplicantPortalService


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        secret="test-secret-do-not-use-in-prod",
        algorithm="HS256",
        access_token_ttl_minutes=15,
    )


@pytest.fixture(autouse=True)
def _override_jwt_settings(monkeypatch: pytest.MonkeyPatch, settings: AuthSettings) -> None:
    monkeypatch.setattr(jwt_module, "_settings", settings)


@pytest.fixture
def service() -> InMemoryApplicantPortalService:
    svc = InMemoryApplicantPortalService()
    return svc


@pytest.fixture
def client(service: InMemoryApplicantPortalService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[router_module.get_service] = lambda: service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _bearer(subject: str, roles: list[str], settings: AuthSettings) -> dict[str, str]:
    token = create_access_token(subject, roles=roles, settings=settings)
    return {"Authorization": f"Bearer {token}"}


def _payload(case_type: str = "INDIVIDUAL", country: str = "GB", fund: str = "FUND-1") -> dict:
    return {
        "case_type": case_type,
        "country_code": country,
        "fund_id": fund,
        "applicant_email": "alice@example.com",
        "applicant_full_name": "Alice Smith",
    }


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.post("/portal/applicant/cases", json=_payload())
    assert response.status_code == 401


def test_non_applicant_role_returns_403(client: TestClient, settings: AuthSettings) -> None:
    response = client.post(
        "/portal/applicant/cases",
        headers=_bearer("rev-1", ["REVIEWER"], settings),
        json=_payload(),
    )
    assert response.status_code == 403


def test_submit_case_happy_path(client: TestClient, settings: AuthSettings) -> None:
    response = client.post(
        "/portal/applicant/cases",
        headers=_bearer(str(uuid4()), ["APPLICANT"], settings),
        json=_payload(case_type="INDIVIDUAL", country="GB"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["case_type"] == "INDIVIDUAL"
    assert body["country_code"] == "GB"
    assert body["status"] == CaseStatus.INITIATED.value


def test_list_cases_scoped_to_applicant(client: TestClient, settings: AuthSettings) -> None:
    alice = str(uuid4())
    bob = str(uuid4())

    client.post("/portal/applicant/cases", headers=_bearer(alice, ["APPLICANT"], settings), json=_payload(country="GB"))
    client.post("/portal/applicant/cases", headers=_bearer(alice, ["APPLICANT"], settings), json=_payload(country="US"))
    client.post("/portal/applicant/cases", headers=_bearer(bob, ["APPLICANT"], settings), json=_payload(country="DE"))

    alice_cases = client.get("/portal/applicant/cases", headers=_bearer(alice, ["APPLICANT"], settings)).json()
    bob_cases = client.get("/portal/applicant/cases", headers=_bearer(bob, ["APPLICANT"], settings)).json()

    assert {c["country_code"] for c in alice_cases} == {"GB", "US"}
    assert {c["country_code"] for c in bob_cases} == {"DE"}


def test_status_lists_pending_documents_for_individual(
    client: TestClient, settings: AuthSettings
) -> None:
    auth = _bearer(str(uuid4()), ["APPLICANT"], settings)
    case_id = client.post("/portal/applicant/cases", headers=auth, json=_payload()).json()["id"]

    response = client.get(f"/portal/applicant/cases/{case_id}/status", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert set(body["documents_pending"]) == {"PASSPORT", "PROOF_OF_ADDRESS"}
    assert body["status"] == CaseStatus.INITIATED.value


def test_status_lists_pending_documents_for_corporate(
    client: TestClient, settings: AuthSettings
) -> None:
    auth = _bearer(str(uuid4()), ["APPLICANT"], settings)
    case_id = client.post(
        "/portal/applicant/cases",
        headers=auth,
        json=_payload(case_type="CORPORATE"),
    ).json()["id"]

    body = client.get(f"/portal/applicant/cases/{case_id}/status", headers=auth).json()

    assert set(body["documents_pending"]) == {
        "CERTIFICATE_OF_INCORPORATION",
        "SHAREHOLDER_REGISTER",
        "PROOF_OF_AUTHORITY",
    }


def test_status_unknown_case_returns_404(client: TestClient, settings: AuthSettings) -> None:
    auth = _bearer(str(uuid4()), ["APPLICANT"], settings)
    response = client.get(f"/portal/applicant/cases/{uuid4()}/status", headers=auth)
    assert response.status_code == 404


def test_other_applicants_case_returns_403(client: TestClient, settings: AuthSettings) -> None:
    alice = _bearer(str(uuid4()), ["APPLICANT"], settings)
    bob = _bearer(str(uuid4()), ["APPLICANT"], settings)
    case_id = client.post("/portal/applicant/cases", headers=alice, json=_payload()).json()["id"]

    response = client.get(f"/portal/applicant/cases/{case_id}/status", headers=bob)

    assert response.status_code == 403


def test_upload_document_advances_status_to_documents_pending(
    client: TestClient, settings: AuthSettings
) -> None:
    auth = _bearer(str(uuid4()), ["APPLICANT"], settings)
    case_id = client.post("/portal/applicant/cases", headers=auth, json=_payload()).json()["id"]

    upload = client.post(
        f"/portal/applicant/cases/{case_id}/documents",
        headers=auth,
        json={
            "doc_type": "PASSPORT",
            "file_name": "passport.pdf",
            "storage_ref": "s3://bucket/passport.pdf",
            "document_number": "P12345",
            "country_of_issue": "GB",
        },
    )

    assert upload.status_code == 201
    assert upload.json()["doc_type"] == "PASSPORT"

    status_resp = client.get(f"/portal/applicant/cases/{case_id}/status", headers=auth).json()
    assert status_resp["status"] == CaseStatus.DOCUMENTS_PENDING.value
    assert "PASSPORT" not in status_resp["documents_pending"]
    assert "PROOF_OF_ADDRESS" in status_resp["documents_pending"]


def test_upload_to_unknown_case_returns_404(client: TestClient, settings: AuthSettings) -> None:
    auth = _bearer(str(uuid4()), ["APPLICANT"], settings)
    response = client.post(
        f"/portal/applicant/cases/{uuid4()}/documents",
        headers=auth,
        json={
            "doc_type": "PASSPORT",
            "file_name": "x.pdf",
            "storage_ref": "s3://bucket/x.pdf",
        },
    )
    assert response.status_code == 404


def test_upload_to_other_applicants_case_returns_403(
    client: TestClient, settings: AuthSettings
) -> None:
    alice = _bearer(str(uuid4()), ["APPLICANT"], settings)
    bob = _bearer(str(uuid4()), ["APPLICANT"], settings)
    case_id = client.post("/portal/applicant/cases", headers=alice, json=_payload()).json()["id"]

    response = client.post(
        f"/portal/applicant/cases/{case_id}/documents",
        headers=bob,
        json={
            "doc_type": "PASSPORT",
            "file_name": "x.pdf",
            "storage_ref": "s3://bucket/x.pdf",
        },
    )
    assert response.status_code == 403


def test_invalid_payload_returns_422(client: TestClient, settings: AuthSettings) -> None:
    auth = _bearer(str(uuid4()), ["APPLICANT"], settings)
    response = client.post(
        "/portal/applicant/cases",
        headers=auth,
        json={
            "case_type": "INDIVIDUAL",
            "country_code": "G",
            "fund_id": "",
            "applicant_email": "not-an-email",
            "applicant_full_name": "",
        },
    )
    assert response.status_code == 422
