from __future__ import annotations
import pytest
from datetime import datetime
from uuid import uuid4

from src.core.domain.kyc_case import RiskTier
from src.kyc.individual.pep_screening import PEPMatch, PEPCategory, PEPScreeningResult
from src.kyc.individual.sanctions import SanctionsHit, SanctionsList, SanctionsScreeningResult
from src.kyc.individual.risk_scoring import (
    HIGH_RISK_COUNTRIES,
    MEDIUM_RISK_COUNTRIES,
    WEIGHT_COUNTRY_RISK,
    WEIGHT_PEP,
    WEIGHT_SANCTIONS,
    WEIGHT_SOURCE_OF_FUNDS,
    score_individual,
)


def _clean_pep(applicant_id) -> PEPScreeningResult:
    return PEPScreeningResult(
        applicant_id=applicant_id,
        screened_at=datetime.utcnow(),
        is_pep=False,
    )


def _pep_hit(applicant_id) -> PEPScreeningResult:
    match = PEPMatch(
        matched_name="Ali Hassan",
        category=PEPCategory.SENIOR_OFFICIAL,
        country="IR",
        position="Minister",
        match_score=95.0,
        source="Dow Jones",
    )
    return PEPScreeningResult(
        applicant_id=applicant_id,
        screened_at=datetime.utcnow(),
        is_pep=True,
        matches=[match],
        enhanced_due_diligence_required=True,
    )


def _clean_sanctions(applicant_id) -> SanctionsScreeningResult:
    return SanctionsScreeningResult(
        applicant_id=applicant_id,
        screened_at=datetime.utcnow(),
        is_clear=True,
    )


def _sanctions_hit(applicant_id) -> SanctionsScreeningResult:
    hit = SanctionsHit(
        list_name=SanctionsList.OFAC_SDN,
        matched_name="Ali Hassan",
        match_score=98.0,
        reference="SDN-99999",
        details="Designated",
    )
    return SanctionsScreeningResult(
        applicant_id=applicant_id,
        screened_at=datetime.utcnow(),
        is_clear=False,
        hits=[hit],
    )


class TestCountryRiskScoring:
    def test_high_risk_country_scores_90(self, high_risk_applicant):
        profile = score_individual(
            high_risk_applicant,
            _clean_pep(high_risk_applicant.id),
            _clean_sanctions(high_risk_applicant.id),
        )
        country_factor = next(f for f in profile.factors if f.name == "country_risk")
        assert country_factor.score == 90.0

    def test_medium_risk_country_scores_50(self, individual_applicant):
        individual_applicant.country_of_residence = "RU"
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        country_factor = next(f for f in profile.factors if f.name == "country_risk")
        assert country_factor.score == 50.0

    def test_standard_country_scores_10(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        country_factor = next(f for f in profile.factors if f.name == "country_risk")
        assert country_factor.score == 10.0


class TestPEPScoring:
    def test_pep_confirmed_scores_85(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _pep_hit(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        pep_factor = next(f for f in profile.factors if f.name == "pep")
        assert pep_factor.score == 85.0

    def test_no_pep_scores_0(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        pep_factor = next(f for f in profile.factors if f.name == "pep")
        assert pep_factor.score == 0.0


class TestSanctionsScoring:
    def test_sanctions_hit_scores_100(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _sanctions_hit(individual_applicant.id),
        )
        s_factor = next(f for f in profile.factors if f.name == "sanctions")
        assert s_factor.score == 100.0

    def test_no_sanctions_scores_0(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        s_factor = next(f for f in profile.factors if f.name == "sanctions")
        assert s_factor.score == 0.0


class TestSourceOfFundsScoring:
    def test_missing_source_of_funds_scores_40(self, individual_applicant):
        individual_applicant.source_of_funds = None
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        sof_factor = next(f for f in profile.factors if f.name == "source_of_funds")
        assert sof_factor.score == 40.0

    def test_declared_source_of_funds_scores_5(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        sof_factor = next(f for f in profile.factors if f.name == "source_of_funds")
        assert sof_factor.score == 5.0


class TestRiskTierThresholds:
    def test_clean_gb_applicant_is_low_risk(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        assert profile.tier == RiskTier.LOW

    def test_sanctions_hit_elevates_tier_above_low(self, individual_applicant):
        # sanctions weight=0.30, max score=100 → contributes 30 pts → MEDIUM tier
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _sanctions_hit(individual_applicant.id),
        )
        assert profile.tier != RiskTier.LOW

    def test_override_tier_takes_precedence(self, individual_applicant):
        profile = score_individual(
            individual_applicant,
            _clean_pep(individual_applicant.id),
            _clean_sanctions(individual_applicant.id),
        )
        profile.override(RiskTier.VERY_HIGH, reason="Manual escalation", actor="supervisor_1")
        assert profile.tier == RiskTier.VERY_HIGH
