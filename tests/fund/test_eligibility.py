from __future__ import annotations
import pytest
from uuid import uuid4

from src.core.domain.applicant import InvestorClass
from src.core.domain.kyc_case import KYCCase, CaseStatus, CaseType, RiskTier
from src.fund.eligibility import FundType, check_fund_eligibility


def _approved_case(risk_tier: RiskTier = RiskTier.LOW) -> KYCCase:
    case = KYCCase(case_type=CaseType.INDIVIDUAL, country_code="GB", fund_id="FUND-001")
    case.status = CaseStatus.APPROVED
    case.risk_tier = risk_tier
    return case


def _initiated_case() -> KYCCase:
    return KYCCase(case_type=CaseType.INDIVIDUAL, country_code="GB", fund_id="FUND-001")


class TestFundEligibilityMatrix:
    def test_retail_eligible_for_ucits(self):
        assert check_fund_eligibility(_approved_case(), FundType.UCITS, InvestorClass.RETAIL).eligible

    def test_retail_not_eligible_for_aifmd(self):
        result = check_fund_eligibility(_approved_case(), FundType.AIFMD, InvestorClass.RETAIL)
        assert not result.eligible
        assert any("not eligible" in r for r in result.failure_reasons)

    def test_retail_not_eligible_for_hedge_fund(self):
        assert not check_fund_eligibility(_approved_case(), FundType.HEDGE_FUND, InvestorClass.RETAIL).eligible

    def test_professional_eligible_for_ucits_aifmd_and_pe(self):
        for fund in [FundType.UCITS, FundType.AIFMD, FundType.PRIVATE_EQUITY]:
            result = check_fund_eligibility(_approved_case(), fund, InvestorClass.PROFESSIONAL)
            assert result.eligible, f"Expected PROFESSIONAL to be eligible for {fund}"

    def test_professional_not_eligible_for_hedge_fund(self):
        assert not check_fund_eligibility(_approved_case(), FundType.HEDGE_FUND, InvestorClass.PROFESSIONAL).eligible

    def test_institutional_eligible_for_all_fund_types(self):
        for fund_type in FundType:
            result = check_fund_eligibility(_approved_case(), fund_type, InvestorClass.INSTITUTIONAL)
            assert result.eligible, f"Expected INSTITUTIONAL to be eligible for {fund_type}"


class TestCaseStatusGate:
    def test_non_approved_case_is_not_eligible(self):
        result = check_fund_eligibility(_initiated_case(), FundType.UCITS, InvestorClass.RETAIL)
        assert not result.eligible
        assert any("not approved" in r for r in result.failure_reasons)

    def test_approved_case_passes_status_check(self):
        assert check_fund_eligibility(_approved_case(), FundType.UCITS, InvestorClass.RETAIL).eligible


class TestRiskTierGate:
    def test_very_high_risk_blocks_all_funds(self):
        result = check_fund_eligibility(
            _approved_case(RiskTier.VERY_HIGH), FundType.UCITS, InvestorClass.RETAIL
        )
        assert not result.eligible
        assert any("very high risk" in r.lower() for r in result.failure_reasons)

    def test_high_risk_does_not_block(self):
        assert check_fund_eligibility(
            _approved_case(RiskTier.HIGH), FundType.UCITS, InvestorClass.RETAIL
        ).eligible

    def test_low_risk_passes(self):
        assert check_fund_eligibility(
            _approved_case(RiskTier.LOW), FundType.UCITS, InvestorClass.RETAIL
        ).eligible


class TestEligibilityResult:
    def test_result_records_case_fund_and_investor_class(self):
        case = _approved_case()
        result = check_fund_eligibility(case, FundType.AIFMD, InvestorClass.PROFESSIONAL)
        assert result.case_id == case.id
        assert result.fund_type == FundType.AIFMD
        assert result.investor_class == InvestorClass.PROFESSIONAL

    def test_multiple_failures_all_reported(self):
        # Non-approved + retail trying hedge fund → 2 failures
        result = check_fund_eligibility(_initiated_case(), FundType.HEDGE_FUND, InvestorClass.RETAIL)
        assert len(result.failure_reasons) >= 2
