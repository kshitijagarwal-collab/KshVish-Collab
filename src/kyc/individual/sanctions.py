from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID

import httpx

from src.core.domain.applicant import IndividualApplicant


class SanctionsList(str, Enum):
    OFAC_SDN = "OFAC_SDN"
    UN_CONSOLIDATED = "UN_CONSOLIDATED"
    EU_CONSOLIDATED = "EU_CONSOLIDATED"
    UK_HMT = "UK_HMT"
    INTERPOL = "INTERPOL"


@dataclass
class SanctionsHit:
    list_name: SanctionsList
    matched_name: str
    match_score: float
    reference: str
    details: str


@dataclass
class SanctionsScreeningResult:
    applicant_id: UUID
    screened_at: datetime
    is_clear: bool
    hits: list[SanctionsHit] = field(default_factory=list)
    lists_checked: list[SanctionsList] = field(default_factory=list)
    false_positive_cleared: bool = False
    cleared_by: Optional[str] = None
    cleared_reason: Optional[str] = None

    def has_confirmed_hit(self) -> bool:
        return not self.is_clear and not self.false_positive_cleared

    def clear_as_false_positive(self, actor: str, reason: str) -> None:
        self.false_positive_cleared = True
        self.cleared_by = actor
        self.cleared_reason = reason


class SanctionsProvider(Protocol):
    def screen(
        self,
        applicant: IndividualApplicant,
        lists: list[SanctionsList],
    ) -> list[SanctionsHit]: ...


class StubSanctionsProvider:
    def screen(
        self,
        applicant: IndividualApplicant,
        lists: list[SanctionsList],
    ) -> list[SanctionsHit]:
        return []


_LIST_TO_COMPLY_ADVANTAGE = {
    SanctionsList.OFAC_SDN: "ofac-sdn",
    SanctionsList.UN_CONSOLIDATED: "un-consolidated",
    SanctionsList.EU_CONSOLIDATED: "eu-consolidated",
    SanctionsList.UK_HMT: "uk-hmt",
    SanctionsList.INTERPOL: "interpol",
}


@dataclass
class ComplyAdvantageProvider:
    api_key: str
    base_url: str = "https://api.complyadvantage.com"
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def screen(
        self,
        applicant: IndividualApplicant,
        lists: list[SanctionsList],
    ) -> list[SanctionsHit]:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            payload = {
                "search_term": applicant.full_name,
                "client_ref": str(applicant.id),
                "filters": {
                    "types": ["sanction"],
                    "list_codes": [_LIST_TO_COMPLY_ADVANTAGE[ls] for ls in lists],
                },
            }
            response = client.post(
                f"{self.base_url}/searches",
                json=payload,
                headers={"Authorization": f"Token {self.api_key}"},
            )
            response.raise_for_status()
            return _parse_comply_advantage_hits(response.json(), lists)
        finally:
            if self.client is None:
                client.close()


def _parse_comply_advantage_hits(
    body: dict,
    lists: list[SanctionsList],
) -> list[SanctionsHit]:
    list_lookup = {v: k for k, v in _LIST_TO_COMPLY_ADVANTAGE.items()}
    hits: list[SanctionsHit] = []
    for match in body.get("data", {}).get("hits", []):
        list_code = match.get("list_code")
        list_enum = list_lookup.get(list_code)
        if list_enum is None or list_enum not in lists:
            continue
        hits.append(SanctionsHit(
            list_name=list_enum,
            matched_name=match.get("name", ""),
            match_score=float(match.get("score", 0)),
            reference=match.get("reference", ""),
            details=match.get("notes", ""),
        ))
    return hits


@dataclass
class RefinitivProvider:
    api_key: str
    base_url: str = "https://api-worldcheck.refinitiv.com/v2"
    group_id: str = ""
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def screen(
        self,
        applicant: IndividualApplicant,
        lists: list[SanctionsList],
    ) -> list[SanctionsHit]:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            payload = {
                "groupId": self.group_id,
                "name": applicant.full_name,
                "entityType": "INDIVIDUAL",
                "providerTypes": ["SANCTIONS"],
                "secondaryFields": [
                    {"typeId": "SFCT_1", "value": applicant.date_of_birth.isoformat()},
                ],
            }
            response = client.post(
                f"{self.base_url}/cases/screeningRequest",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return _parse_refinitiv_hits(response.json(), lists)
        finally:
            if self.client is None:
                client.close()


_REFINITIV_LIST_MAP = {
    "OFAC": SanctionsList.OFAC_SDN,
    "UN": SanctionsList.UN_CONSOLIDATED,
    "EU": SanctionsList.EU_CONSOLIDATED,
    "HMT": SanctionsList.UK_HMT,
    "INTERPOL": SanctionsList.INTERPOL,
}


def _parse_refinitiv_hits(
    body: dict,
    lists: list[SanctionsList],
) -> list[SanctionsHit]:
    hits: list[SanctionsHit] = []
    for result in body.get("results", []):
        for source in result.get("sources", []):
            list_enum = _REFINITIV_LIST_MAP.get(source.get("type"))
            if list_enum is None or list_enum not in lists:
                continue
            hits.append(SanctionsHit(
                list_name=list_enum,
                matched_name=result.get("matchedTerm", ""),
                match_score=float(result.get("matchStrength", 0)),
                reference=result.get("referenceId", ""),
                details=source.get("description", ""),
            ))
    return hits


def screen_individual(
    applicant: IndividualApplicant,
    lists: list[SanctionsList] | None = None,
    provider: SanctionsProvider | None = None,
) -> SanctionsScreeningResult:
    if lists is None:
        lists = list(SanctionsList)

    selected = provider or _get_provider()
    hits = selected.screen(applicant, lists)
    is_clear = len(hits) == 0

    return SanctionsScreeningResult(
        applicant_id=applicant.id,
        screened_at=datetime.utcnow(),
        is_clear=is_clear,
        hits=hits,
        lists_checked=lists,
    )


def _query_sanctions_providers(
    applicant: IndividualApplicant,
    lists: list[SanctionsList],
) -> list[SanctionsHit]:
    return _get_provider().screen(applicant, lists)


def _get_provider() -> SanctionsProvider:
    name = os.getenv("KYC_SANCTIONS_PROVIDER", "stub").lower()
    if name == "comply_advantage":
        return ComplyAdvantageProvider(api_key=os.environ["KYC_COMPLY_ADVANTAGE_API_KEY"])
    if name == "refinitiv":
        return RefinitivProvider(
            api_key=os.environ["KYC_REFINITIV_API_KEY"],
            group_id=os.environ.get("KYC_REFINITIV_GROUP_ID", ""),
        )
    return StubSanctionsProvider()
