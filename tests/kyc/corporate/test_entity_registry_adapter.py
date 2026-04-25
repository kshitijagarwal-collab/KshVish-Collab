from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import httpx
import pytest

from src.core.domain.applicant import Address, CorporateApplicant
from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.kyc.corporate.entity_verification import (
    CompaniesHouseProvider,
    EntityRegistryProvider,
    OpenCorporatesProvider,
    RegistryRecord,
    StubEntityRegistryProvider,
    _get_provider,
    verify_entity,
)


def _applicant() -> CorporateApplicant:
    return CorporateApplicant(
        legal_name="Acme Ltd",
        registration_number="12345678",
        country_of_incorporation="GB",
        registered_address=Address(
            line1="1 High St",
            city="London",
            country_code="GB",
            postal_code="SW1A 1AA",
        ),
        regulated=False,
    )


def _verified_inc_doc(applicant_id) -> Document:
    return Document(
        case_id=uuid4(),
        applicant_id=applicant_id,
        doc_type=DocumentType.CERTIFICATE_OF_INCORPORATION,
        file_name="cert.pdf",
        storage_ref="s3://bucket/cert.pdf",
        status=DocumentStatus.VERIFIED,
        verified_at=datetime.utcnow(),
    )


class _RecordingProvider:
    def __init__(self, record: RegistryRecord) -> None:
        self.record = record
        self.calls: list[str] = []

    def lookup(self, applicant: CorporateApplicant) -> RegistryRecord:
        self.calls.append(applicant.registration_number)
        return self.record


def test_missing_incorporation_doc_fails_before_lookup() -> None:
    rec = _RecordingProvider(RegistryRecord(confirmed=True, source="X"))
    result = verify_entity(_applicant(), documents=[], provider=rec)

    assert result.passed is False
    assert "Missing verified incorporation documents" in (result.failure_reason or "")
    assert rec.calls == []


def test_unverified_doc_does_not_count() -> None:
    applicant = _applicant()
    doc = _verified_inc_doc(applicant.id)
    doc.status = DocumentStatus.UPLOADED
    rec = _RecordingProvider(RegistryRecord(confirmed=True, source="X"))

    result = verify_entity(applicant, documents=[doc], provider=rec)

    assert result.passed is False


def test_doc_for_other_applicant_does_not_count() -> None:
    applicant = _applicant()
    other_doc = _verified_inc_doc(uuid4())
    rec = _RecordingProvider(RegistryRecord(confirmed=True, source="X"))

    result = verify_entity(applicant, documents=[other_doc], provider=rec)

    assert result.passed is False


def test_registry_unconfirmed_fails() -> None:
    applicant = _applicant()
    rec = _RecordingProvider(RegistryRecord(confirmed=False, source="COMPANIES_HOUSE"))

    result = verify_entity(applicant, documents=[_verified_inc_doc(applicant.id)], provider=rec)

    assert result.passed is False
    assert "Entity not found" in (result.failure_reason or "")


def test_happy_path_passes() -> None:
    applicant = _applicant()
    applicant.regulated = True
    applicant.regulator = "FCA-123"
    rec = _RecordingProvider(RegistryRecord(
        confirmed=True,
        source="COMPANIES_HOUSE",
        legal_name="Acme Ltd",
        status="active",
    ))

    result = verify_entity(applicant, documents=[_verified_inc_doc(applicant.id)], provider=rec)

    assert result.passed is True
    assert result.registry_confirmed is True
    assert result.is_regulated_entity is True
    assert result.regulator_reference == "FCA-123"


def test_factory_defaults_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KYC_ENTITY_REGISTRY_PROVIDER", raising=False)
    assert isinstance(_get_provider(), StubEntityRegistryProvider)


def test_factory_selects_companies_house(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_ENTITY_REGISTRY_PROVIDER", "companies_house")
    monkeypatch.setenv("KYC_COMPANIES_HOUSE_API_KEY", "ch-key")
    provider = _get_provider()
    assert isinstance(provider, CompaniesHouseProvider)
    assert provider.api_key == "ch-key"


def test_factory_selects_open_corporates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_ENTITY_REGISTRY_PROVIDER", "open_corporates")
    monkeypatch.delenv("KYC_OPEN_CORPORATES_API_KEY", raising=False)
    provider = _get_provider()
    assert isinstance(provider, OpenCorporatesProvider)
    assert provider.api_key is None


def test_companies_house_active_returns_confirmed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "company_name": "Acme Ltd",
            "company_status": "active",
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CompaniesHouseProvider(api_key="k", client=client)

    record = provider.lookup(_applicant())

    assert record.confirmed is True
    assert record.legal_name == "Acme Ltd"
    assert record.status == "active"


def test_companies_house_dissolved_returns_unconfirmed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "company_name": "Acme Ltd",
            "company_status": "dissolved",
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CompaniesHouseProvider(api_key="k", client=client)

    record = provider.lookup(_applicant())

    assert record.confirmed is False


def test_companies_house_404_returns_unconfirmed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CompaniesHouseProvider(api_key="k", client=client)

    record = provider.lookup(_applicant())

    assert record.confirmed is False
    assert record.source == "COMPANIES_HOUSE"


def test_open_corporates_active() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "results": {
                "company": {"name": "Acme Ltd", "inactive": False}
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenCorporatesProvider(client=client)

    record = provider.lookup(_applicant())

    assert record.confirmed is True
    assert record.status == "active"


def test_open_corporates_inactive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "results": {
                "company": {"name": "Acme Ltd", "inactive": True}
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenCorporatesProvider(client=client)

    record = provider.lookup(_applicant())

    assert record.confirmed is False


def test_protocol_compliance() -> None:
    p: EntityRegistryProvider = StubEntityRegistryProvider()
    assert p.lookup(_applicant()).confirmed is True
