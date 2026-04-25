from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class CaseStatus(str, Enum):
    INITIATED = "INITIATED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    IN_REVIEW = "IN_REVIEW"
    PENDING_INFO = "PENDING_INFO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class CaseType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    CORPORATE = "CORPORATE"
    INSTITUTIONAL = "INSTITUTIONAL"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


@dataclass
class KYCCase:
    case_type: CaseType
    country_code: str
    fund_id: str
    id: UUID = field(default_factory=uuid4)
    status: CaseStatus = CaseStatus.INITIATED
    risk_tier: Optional[RiskTier] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    reviewer_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    expiry_date: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def transition(self, new_status: CaseStatus, actor: str, reason: str = "") -> None:
        from src.core.workflow.state_machine import validate_transition
        validate_transition(self.status, new_status)
        self.status = new_status
        self.updated_at = datetime.utcnow()
        self.metadata[f"transition_{datetime.utcnow().isoformat()}"] = {
            "from": self.status,
            "to": new_status,
            "actor": actor,
            "reason": reason,
        }

    def assign_risk(self, tier: RiskTier) -> None:
        self.risk_tier = tier
        self.updated_at = datetime.utcnow()

    def is_active(self) -> bool:
        return self.status not in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.EXPIRED)

    def is_approved(self) -> bool:
        return self.status == CaseStatus.APPROVED
