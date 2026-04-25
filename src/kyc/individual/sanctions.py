from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

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


def screen_individual(
    applicant: IndividualApplicant,
    lists: list[SanctionsList] | None = None,
) -> SanctionsScreeningResult:
    if lists is None:
        lists = list(SanctionsList)

    hits = _query_sanctions_providers(applicant, lists)
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
    # Integration point: replace with real provider calls (e.g. ComplyAdvantage, Refinitiv)
    return []
