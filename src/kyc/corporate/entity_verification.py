from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

import httpx

from src.core.domain.applicant import CorporateApplicant
from src.core.domain.document import Document, DocumentStatus, DocumentType


INCORPORATION_DOC_TYPES = {
    DocumentType.CERTIFICATE_OF_INCORPORATION,
    DocumentType.ARTICLES_OF_ASSOCIATION,
}


@dataclass
class RegistryRecord:
    confirmed: bool
    source: str
    legal_name: Optional[str] = None
    status: Optional[str] = None
    is_regulated: bool = False
    regulator_reference: Optional[str] = None


@dataclass
class EntityVerificationResult:
    applicant_id: UUID
    verified_at: datetime
    passed: bool
    failure_reason: Optional[str] = None
    registry_confirmed: bool = False
    is_regulated_entity: bool = False
    regulator_reference: Optional[str] = None


class EntityRegistryProvider(Protocol):
    def lookup(self, applicant: CorporateApplicant) -> RegistryRecord: ...


class StubEntityRegistryProvider:
    def lookup(self, applicant: CorporateApplicant) -> RegistryRecord:
        return RegistryRecord(
            confirmed=True,
            source="STUB",
            legal_name=applicant.legal_name,
            is_regulated=applicant.regulated,
            regulator_reference=applicant.regulator,
        )


@dataclass
class CompaniesHouseProvider:
    api_key: str
    base_url: str = "https://api.company-information.service.gov.uk"
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def lookup(self, applicant: CorporateApplicant) -> RegistryRecord:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            response = client.get(
                f"{self.base_url}/company/{applicant.registration_number}",
                auth=(self.api_key, ""),
            )
            if response.status_code == 404:
                return RegistryRecord(confirmed=False, source="COMPANIES_HOUSE")
            response.raise_for_status()
            return _parse_companies_house(response.json())
        finally:
            if self.client is None:
                client.close()


def _parse_companies_house(body: dict) -> RegistryRecord:
    status = body.get("company_status", "")
    is_active = status == "active"
    return RegistryRecord(
        confirmed=is_active,
        source="COMPANIES_HOUSE",
        legal_name=body.get("company_name"),
        status=status,
        is_regulated=False,
        regulator_reference=None,
    )


@dataclass
class OpenCorporatesProvider:
    api_key: Optional[str] = None
    base_url: str = "https://api.opencorporates.com/v0.4"
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def lookup(self, applicant: CorporateApplicant) -> RegistryRecord:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            jurisdiction = applicant.country_of_incorporation.lower()
            params = {"api_token": self.api_key} if self.api_key else {}
            response = client.get(
                f"{self.base_url}/companies/{jurisdiction}/{applicant.registration_number}",
                params=params,
            )
            if response.status_code == 404:
                return RegistryRecord(confirmed=False, source="OPEN_CORPORATES")
            response.raise_for_status()
            return _parse_open_corporates(response.json())
        finally:
            if self.client is None:
                client.close()


def _parse_open_corporates(body: dict) -> RegistryRecord:
    company = body.get("results", {}).get("company", {})
    inactive = bool(company.get("inactive", False))
    return RegistryRecord(
        confirmed=bool(company) and not inactive,
        source="OPEN_CORPORATES",
        legal_name=company.get("name"),
        status="inactive" if inactive else "active",
        is_regulated=False,
        regulator_reference=None,
    )


def verify_entity(
    applicant: CorporateApplicant,
    documents: list[Document],
    provider: EntityRegistryProvider | None = None,
) -> EntityVerificationResult:
    now = datetime.utcnow()

    inc_docs = [
        d for d in documents
        if d.doc_type in INCORPORATION_DOC_TYPES
        and d.applicant_id == applicant.id
        and d.status == DocumentStatus.VERIFIED
    ]

    if not inc_docs:
        return EntityVerificationResult(
            applicant_id=applicant.id,
            verified_at=now,
            passed=False,
            failure_reason="Missing verified incorporation documents",
        )

    record = (provider or _get_provider()).lookup(applicant)
    if not record.confirmed:
        return EntityVerificationResult(
            applicant_id=applicant.id,
            verified_at=now,
            passed=False,
            failure_reason="Entity not found or details mismatch in company registry",
        )

    return EntityVerificationResult(
        applicant_id=applicant.id,
        verified_at=now,
        passed=True,
        registry_confirmed=True,
        is_regulated_entity=applicant.regulated,
        regulator_reference=applicant.regulator,
    )


def _check_company_registry(applicant: CorporateApplicant) -> bool:
    return _get_provider().lookup(applicant).confirmed


def _get_provider() -> EntityRegistryProvider:
    name = os.getenv("KYC_ENTITY_REGISTRY_PROVIDER", "stub").lower()
    if name == "companies_house":
        return CompaniesHouseProvider(api_key=os.environ["KYC_COMPANIES_HOUSE_API_KEY"])
    if name == "open_corporates":
        return OpenCorporatesProvider(api_key=os.environ.get("KYC_OPEN_CORPORATES_API_KEY"))
    return StubEntityRegistryProvider()
