from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_individual_case(client: TestClient, sample_individual_payload: dict) -> None:
    response = client.post("/cases", json=sample_individual_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["case_type"] == "INDIVIDUAL"
    assert body["country_code"] == "GB"
    assert body["status"] == "INITIATED"
    assert body["applicant_id"] is not None


def test_create_corporate_case(client: TestClient, sample_corporate_payload: dict) -> None:
    response = client.post("/cases", json=sample_corporate_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["case_type"] == "CORPORATE"
    assert body["applicant_id"] is not None


def test_create_individual_without_applicant_data_returns_422(client: TestClient) -> None:
    response = client.post(
        "/cases",
        json={"case_type": "INDIVIDUAL", "country_code": "GB", "fund_id": "FUND-001"},
    )
    assert response.status_code == 422


def test_create_corporate_without_applicant_data_returns_422(client: TestClient) -> None:
    response = client.post(
        "/cases",
        json={"case_type": "CORPORATE", "country_code": "GB", "fund_id": "FUND-001"},
    )
    assert response.status_code == 422


def test_get_case(client: TestClient, sample_individual_payload: dict) -> None:
    created = client.post("/cases", json=sample_individual_payload).json()
    case_id = created["case_id"]

    response = client.get(f"/cases/{case_id}")
    assert response.status_code == 200
    assert response.json()["case_id"] == case_id


def test_get_case_unknown_returns_404(client: TestClient) -> None:
    response = client.get(f"/cases/{uuid4()}")
    assert response.status_code == 404


def test_create_case_normalizes_country_code_to_upper(
    client: TestClient, sample_individual_payload: dict
) -> None:
    payload = {**sample_individual_payload, "country_code": "gb"}
    response = client.post("/cases", json=payload)
    assert response.status_code == 201
    assert response.json()["country_code"] == "GB"
