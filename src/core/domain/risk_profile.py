from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.core.domain.kyc_case import RiskTier


@dataclass
class RiskFactor:
    name: str
    score: float
    weight: float
    reason: str


@dataclass
class RiskProfile:
    case_id: UUID
    applicant_id: UUID
    factors: list[RiskFactor] = field(default_factory=list)
    computed_at: datetime = field(default_factory=datetime.utcnow)
    override_tier: Optional[RiskTier] = None
    override_reason: Optional[str] = None
    override_by: Optional[str] = None

    def add_factor(self, factor: RiskFactor) -> None:
        self.factors.append(factor)

    @property
    def weighted_score(self) -> float:
        if not self.factors:
            return 0.0
        total_weight = sum(f.weight for f in self.factors)
        if total_weight == 0:
            return 0.0
        return sum(f.score * f.weight for f in self.factors) / total_weight

    @property
    def tier(self) -> RiskTier:
        if self.override_tier:
            return self.override_tier
        score = self.weighted_score
        if score >= 80:
            return RiskTier.VERY_HIGH
        if score >= 60:
            return RiskTier.HIGH
        if score >= 30:
            return RiskTier.MEDIUM
        return RiskTier.LOW

    def override(self, tier: RiskTier, reason: str, actor: str) -> None:
        self.override_tier = tier
        self.override_reason = reason
        self.override_by = actor
