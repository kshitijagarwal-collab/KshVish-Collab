from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from src.core.domain.applicant import InvestorClass
from src.core.domain.kyc_case import KYCCase, CaseStatus, RiskTier


class FundType(str, Enum):
    UCITS = "UCITS"
    AIFMD = "AIFMD"
    PRIVATE_EQUITY = "PRIVATE_EQUITY"
    HEDGE_FUND = "HEDGE_FUND"
    VENTURE_CAPITAL = "VENTURE_CAPITAL"
    REAL_ESTATE = "REAL_ESTATE"
    MONEY_MARKET = "MONEY_MARKET"


# MiFID II / AIFMD eligibility matrix
FUND_ELIGIBILITY: dict[FundType, set[InvestorClass]] = {
    FundType.UCITS: {
        InvestorClass.RETAIL,
        InvestorClass.PROFESSIONAL,
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
    FundType.AIFMD: {
        InvestorClass.PROFESSIONAL,
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
    FundType.PRIVATE_EQUITY: {
        InvestorClass.PROFESSIONAL,
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
    FundType.HEDGE_FUND: {
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
    FundType.VENTURE_CAPITAL: {
        InvestorClass.PROFESSIONAL,
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
    FundType.REAL_ESTATE: {
        InvestorClass.PROFESSIONAL,
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
    FundType.MONEY_MARKET: {
        InvestorClass.RETAIL,
        InvestorClass.PROFESSIONAL,
        InvestorClass.ELIGIBLE_COUNTERPARTY,
        InvestorClass.INSTITUTIONAL,
    },
}


@dataclass
class EligibilityResult:
    case_id: UUID
    fund_type: FundType
    investor_class: InvestorClass
    eligible: bool
    failure_reasons: list[str] = field(default_factory=list)


def check_fund_eligibility(
    case: KYCCase,
    fund_type: FundType,
    investor_class: InvestorClass,
) -> EligibilityResult:
    reasons: list[str] = []

    if case.status != CaseStatus.APPROVED:
        reasons.append(f"KYC case not approved — current status: {case.status}")

    allowed_classes = FUND_ELIGIBILITY.get(fund_type, set())
    if investor_class not in allowed_classes:
        reasons.append(
            f"{investor_class} investors are not eligible for {fund_type} funds"
        )

    if case.risk_tier == RiskTier.VERY_HIGH:
        reasons.append("Very high risk tier requires manual fund manager approval")

    return EligibilityResult(
        case_id=case.id,
        fund_type=fund_type,
        investor_class=investor_class,
        eligible=len(reasons) == 0,
        failure_reasons=reasons,
    )
