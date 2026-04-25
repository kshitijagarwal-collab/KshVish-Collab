from __future__ import annotations
import pytest

from src.core.domain.applicant import InvestorClass
from src.kyc.individual.suitability import (
    INSTITUTIONAL_AUM_THRESHOLD,
    PROFESSIONAL_NET_WORTH_THRESHOLD,
    PROFESSIONAL_TRANSACTION_COUNT,
    classify_investor,
)


class TestClassifyInvestor:
    def test_no_criteria_classifies_as_retail(self, individual_applicant):
        result = classify_investor(individual_applicant)
        assert result.investor_class == InvestorClass.RETAIL
        assert result.passed
        assert "UCITS" in result.eligible_fund_types

    def test_institutional_by_net_worth(self, individual_applicant):
        result = classify_investor(
            individual_applicant, net_worth=float(INSTITUTIONAL_AUM_THRESHOLD)
        )
        assert result.investor_class == InvestorClass.INSTITUTIONAL
        assert "PRIVATE_EQUITY" in result.eligible_fund_types
        assert "HEDGE_FUND" in result.eligible_fund_types

    def test_professional_requires_two_criteria(self, individual_applicant):
        result = classify_investor(
            individual_applicant,
            net_worth=float(PROFESSIONAL_NET_WORTH_THRESHOLD),
            transaction_count=PROFESSIONAL_TRANSACTION_COUNT,
        )
        assert result.investor_class == InvestorClass.PROFESSIONAL
        assert "AIFMD" in result.eligible_fund_types

    def test_one_professional_criterion_stays_retail(self, individual_applicant):
        result = classify_investor(
            individual_applicant,
            net_worth=float(PROFESSIONAL_NET_WORTH_THRESHOLD),
        )
        assert result.investor_class == InvestorClass.RETAIL

    def test_works_in_finance_counts_as_one_criterion(self, individual_applicant):
        result = classify_investor(
            individual_applicant,
            net_worth=float(PROFESSIONAL_NET_WORTH_THRESHOLD),
            works_in_finance=True,
        )
        assert result.investor_class == InvestorClass.PROFESSIONAL

    def test_high_net_worth_below_institutional_is_not_institutional(self, individual_applicant):
        result = classify_investor(
            individual_applicant,
            net_worth=float(INSTITUTIONAL_AUM_THRESHOLD) - 1,
            transaction_count=PROFESSIONAL_TRANSACTION_COUNT,
            works_in_finance=True,
        )
        assert result.investor_class == InvestorClass.PROFESSIONAL

    def test_institutional_takes_precedence_over_professional_criteria(self, individual_applicant):
        result = classify_investor(
            individual_applicant,
            net_worth=float(INSTITUTIONAL_AUM_THRESHOLD),
            transaction_count=PROFESSIONAL_TRANSACTION_COUNT,
            works_in_finance=True,
        )
        assert result.investor_class == InvestorClass.INSTITUTIONAL

    def test_retail_only_eligible_for_ucits(self, individual_applicant):
        result = classify_investor(individual_applicant)
        assert result.eligible_fund_types == ["UCITS"]
