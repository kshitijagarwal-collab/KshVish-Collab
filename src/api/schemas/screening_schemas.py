from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from src.kyc.individual.pep_screening import PEPCategory
from src.kyc.individual.sanctions import SanctionsList
from src.core.domain.kyc_case import RiskTier


class SanctionsHitSchema(BaseModel):
    list_name: SanctionsList
    matched_name: str
    match_score: float
    reference: str


class PEPMatchSchema(BaseModel):
    matched_name: str
    category: PEPCategory
    country: str
    position: str
    match_score: float


class ScreeningResponse(BaseModel):
    case_id: UUID
    screened_at: datetime
    identity_passed: bool
    identity_failure: Optional[str]
    sanctions_clear: bool
    sanctions_hits: list[SanctionsHitSchema]
    is_pep: bool
    pep_matches: list[PEPMatchSchema]
    edd_required: bool
    risk_tier: Optional[RiskTier]
    weighted_score: Optional[float]
