from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.core.domain.applicant import IndividualApplicant, InvestorClass


@dataclass
class SuitabilityResult:
    applicant_id: UUID
    investor_class: InvestorClass
    passed: bool
    failure_reason: Optional[str] = None
    eligible_fund_types: Optional[list[str]] = None

    def __post_init__(self) -> None:
        if self.eligible_fund_types is None:
            self.eligible_fund_types = []


# Per MiFID II / AIFMD classification criteria
PROFESSIONAL_NET_WORTH_THRESHOLD = 500_000
PROFESSIONAL_TRANSACTION_COUNT = 10
INSTITUTIONAL_AUM_THRESHOLD = 10_000_000


def classify_investor(
    applicant: IndividualApplicant,
    net_worth: Optional[float] = None,
    transaction_count: Optional[int] = None,
    works_in_finance: bool = False,
) -> SuitabilityResult:
    if _qualifies_institutional(net_worth):
        return SuitabilityResult(
            applicant_id=applicant.id,
            investor_class=InvestorClass.INSTITUTIONAL,
            passed=True,
            eligible_fund_types=["UCITS", "AIFMD", "PRIVATE_EQUITY", "HEDGE_FUND"],
        )

    if _qualifies_professional(net_worth, transaction_count, works_in_finance):
        return SuitabilityResult(
            applicant_id=applicant.id,
            investor_class=InvestorClass.PROFESSIONAL,
            passed=True,
            eligible_fund_types=["UCITS", "AIFMD"],
        )

    return SuitabilityResult(
        applicant_id=applicant.id,
        investor_class=InvestorClass.RETAIL,
        passed=True,
        eligible_fund_types=["UCITS"],
    )


def _qualifies_professional(
    net_worth: Optional[float],
    transaction_count: Optional[int],
    works_in_finance: bool,
) -> bool:
    criteria_met = 0
    if net_worth and net_worth >= PROFESSIONAL_NET_WORTH_THRESHOLD:
        criteria_met += 1
    if transaction_count and transaction_count >= PROFESSIONAL_TRANSACTION_COUNT:
        criteria_met += 1
    if works_in_finance:
        criteria_met += 1
    return criteria_met >= 2


def _qualifies_institutional(net_worth: Optional[float]) -> bool:
    return net_worth is not None and net_worth >= INSTITUTIONAL_AUM_THRESHOLD
