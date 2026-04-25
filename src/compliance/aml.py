from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class AMLFlag(str, Enum):
    STRUCTURING = "STRUCTURING"
    RAPID_MOVEMENT = "RAPID_MOVEMENT"
    HIGH_RISK_JURISDICTION = "HIGH_RISK_JURISDICTION"
    UNUSUAL_SOURCE_OF_FUNDS = "UNUSUAL_SOURCE_OF_FUNDS"
    PEP_LINKED = "PEP_LINKED"
    SANCTIONS_ADJACENT = "SANCTIONS_ADJACENT"
    ADVERSE_MEDIA = "ADVERSE_MEDIA"


class STRStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    FILED = "FILED"
    DISMISSED = "DISMISSED"


@dataclass
class AMLFlag_:
    flag_type: AMLFlag
    description: str
    detected_at: datetime = field(default_factory=datetime.utcnow)
    auto_detected: bool = True


@dataclass
class SuspiciousTransactionReport:
    case_id: UUID
    applicant_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: STRStatus = STRStatus.DRAFT
    flags: list[AMLFlag_] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    filed_at: Optional[datetime] = None
    filed_by: Optional[str] = None
    regulator_reference: Optional[str] = None
    narrative: str = ""

    def add_flag(self, flag: AMLFlag_) -> None:
        self.flags.append(flag)

    def file(self, actor: str, reference: str) -> None:
        self.status = STRStatus.FILED
        self.filed_at = datetime.utcnow()
        self.filed_by = actor
        self.regulator_reference = reference

    def dismiss(self, reason: str) -> None:
        self.status = STRStatus.DISMISSED
        self.narrative = reason


@dataclass
class AMLScreeningResult:
    case_id: UUID
    applicant_id: UUID
    screened_at: datetime
    flags: list[AMLFlag_] = field(default_factory=list)
    str_required: bool = False
    str_id: Optional[UUID] = None

    def flag_count(self) -> int:
        return len(self.flags)


def run_aml_screening(
    case_id: UUID,
    applicant_id: UUID,
    context: dict,
) -> AMLScreeningResult:
    result = AMLScreeningResult(
        case_id=case_id,
        applicant_id=applicant_id,
        screened_at=datetime.utcnow(),
    )

    for detector in _AML_DETECTORS:
        flag = detector(context)
        if flag:
            result.flags.append(flag)

    result.str_required = len(result.flags) >= 2
    return result


def _detect_high_risk_jurisdiction(context: dict) -> Optional[AMLFlag_]:
    from src.kyc.individual.risk_scoring import HIGH_RISK_COUNTRIES
    country = context.get("country_code", "")
    if country in HIGH_RISK_COUNTRIES:
        return AMLFlag_(
            flag_type=AMLFlag.HIGH_RISK_JURISDICTION,
            description=f"Applicant from FATF high-risk jurisdiction: {country}",
        )
    return None


def _detect_pep_linked(context: dict) -> Optional[AMLFlag_]:
    if context.get("is_pep"):
        return AMLFlag_(
            flag_type=AMLFlag.PEP_LINKED,
            description="Applicant is a Politically Exposed Person",
        )
    return None


_AML_DETECTORS = [
    _detect_high_risk_jurisdiction,
    _detect_pep_linked,
]
