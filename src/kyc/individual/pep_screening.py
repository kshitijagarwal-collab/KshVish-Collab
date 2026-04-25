from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from src.core.domain.applicant import IndividualApplicant


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


def screen_pep(applicant: IndividualApplicant) -> PEPScreeningResult:
    matches = _query_pep_providers(applicant)
    is_pep = any(m.match_score >= 85.0 for m in matches)

    return PEPScreeningResult(
        applicant_id=applicant.id,
        screened_at=datetime.utcnow(),
        is_pep=is_pep,
        matches=matches,
        enhanced_due_diligence_required=is_pep,
    )


def _query_pep_providers(applicant: IndividualApplicant) -> list[PEPMatch]:
    # Integration point: replace with real provider (e.g. Dow Jones, LexisNexis)
    return []
