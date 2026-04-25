from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID

import httpx

from src.core.domain.applicant import IndividualApplicant


PEP_MATCH_THRESHOLD = 85.0


class PEPCategory(str, Enum):
    HEAD_OF_STATE = "HEAD_OF_STATE"
    SENIOR_OFFICIAL = "SENIOR_OFFICIAL"
    JUDICIAL = "JUDICIAL"
    MILITARY = "MILITARY"
    STATE_OWNED_ENTERPRISE = "STATE_OWNED_ENTERPRISE"
    FAMILY_MEMBER = "FAMILY_MEMBER"
    CLOSE_ASSOCIATE = "CLOSE_ASSOCIATE"


@dataclass
class PEPMatch:
    matched_name: str
    category: PEPCategory
    country: str
    position: str
    match_score: float
    source: str
    active: bool = True


@dataclass
class PEPScreeningResult:
    applicant_id: UUID
    screened_at: datetime
    is_pep: bool
    matches: list[PEPMatch] = field(default_factory=list)
    enhanced_due_diligence_required: bool = False
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None

    def confirm_pep(self, reviewer: str, notes: str) -> None:
        self.is_pep = True
        self.enhanced_due_diligence_required = True
        self.reviewed_by = reviewer
        self.review_notes = notes

    def clear_false_positive(self, reviewer: str, notes: str) -> None:
        self.is_pep = False
        self.matches = []
        self.reviewed_by = reviewer
        self.review_notes = notes


class PEPProvider(Protocol):
    def query(self, applicant: IndividualApplicant) -> list[PEPMatch]: ...


class StubPEPProvider:
    def query(self, applicant: IndividualApplicant) -> list[PEPMatch]:
        return []


_DOW_JONES_CATEGORY_MAP = {
    "HOS": PEPCategory.HEAD_OF_STATE,
    "SO": PEPCategory.SENIOR_OFFICIAL,
    "JUD": PEPCategory.JUDICIAL,
    "MIL": PEPCategory.MILITARY,
    "SOE": PEPCategory.STATE_OWNED_ENTERPRISE,
    "FAM": PEPCategory.FAMILY_MEMBER,
    "ASC": PEPCategory.CLOSE_ASSOCIATE,
}


@dataclass
class DowJonesProvider:
    api_key: str
    base_url: str = "https://api.djrc.com/risk-and-compliance/v1"
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def query(self, applicant: IndividualApplicant) -> list[PEPMatch]:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            response = client.post(
                f"{self.base_url}/persons/search",
                json={
                    "name": applicant.full_name,
                    "dateOfBirth": applicant.date_of_birth.isoformat(),
                    "categoryFilter": ["PEP"],
                },
                headers={"x-api-key": self.api_key},
            )
            response.raise_for_status()
            return _parse_dow_jones_matches(response.json())
        finally:
            if self.client is None:
                client.close()


def _parse_dow_jones_matches(body: dict) -> list[PEPMatch]:
    matches: list[PEPMatch] = []
    for record in body.get("matches", []):
        category = _DOW_JONES_CATEGORY_MAP.get(record.get("categoryCode", ""))
        if category is None:
            continue
        matches.append(PEPMatch(
            matched_name=record.get("name", ""),
            category=category,
            country=record.get("country", ""),
            position=record.get("position", ""),
            match_score=float(record.get("score", 0)),
            source="DOW_JONES",
            active=bool(record.get("active", True)),
        ))
    return matches


_LEXIS_NEXIS_CATEGORY_MAP = {
    "HEAD_OF_STATE": PEPCategory.HEAD_OF_STATE,
    "SENIOR_GOVT": PEPCategory.SENIOR_OFFICIAL,
    "JUDICIAL": PEPCategory.JUDICIAL,
    "MILITARY": PEPCategory.MILITARY,
    "STATE_ENTERPRISE": PEPCategory.STATE_OWNED_ENTERPRISE,
    "RELATIVE": PEPCategory.FAMILY_MEMBER,
    "ASSOCIATE": PEPCategory.CLOSE_ASSOCIATE,
}


@dataclass
class LexisNexisProvider:
    api_key: str
    base_url: str = "https://bridger.lexisnexis.com/v2"
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def query(self, applicant: IndividualApplicant) -> list[PEPMatch]:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            response = client.post(
                f"{self.base_url}/screen",
                json={
                    "fullName": applicant.full_name,
                    "dob": applicant.date_of_birth.isoformat(),
                    "watchlists": ["PEP"],
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return _parse_lexis_nexis_matches(response.json())
        finally:
            if self.client is None:
                client.close()


def _parse_lexis_nexis_matches(body: dict) -> list[PEPMatch]:
    matches: list[PEPMatch] = []
    for record in body.get("results", []):
        category = _LEXIS_NEXIS_CATEGORY_MAP.get(record.get("pepRole", ""))
        if category is None:
            continue
        matches.append(PEPMatch(
            matched_name=record.get("name", ""),
            category=category,
            country=record.get("countryCode", ""),
            position=record.get("title", ""),
            match_score=float(record.get("matchScore", 0)),
            source="LEXIS_NEXIS",
            active=bool(record.get("isActive", True)),
        ))
    return matches


def screen_pep(
    applicant: IndividualApplicant,
    provider: PEPProvider | None = None,
) -> PEPScreeningResult:
    selected = provider or _get_provider()
    matches = selected.query(applicant)
    is_pep = any(m.match_score >= PEP_MATCH_THRESHOLD for m in matches)

    return PEPScreeningResult(
        applicant_id=applicant.id,
        screened_at=datetime.utcnow(),
        is_pep=is_pep,
        matches=matches,
        enhanced_due_diligence_required=is_pep,
    )


def _query_pep_providers(applicant: IndividualApplicant) -> list[PEPMatch]:
    return _get_provider().query(applicant)


def _get_provider() -> PEPProvider:
    name = os.getenv("KYC_PEP_PROVIDER", "stub").lower()
    if name == "dow_jones":
        return DowJonesProvider(api_key=os.environ["KYC_DOW_JONES_API_KEY"])
    if name == "lexis_nexis":
        return LexisNexisProvider(api_key=os.environ["KYC_LEXIS_NEXIS_API_KEY"])
    return StubPEPProvider()
