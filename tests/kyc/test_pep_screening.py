from __future__ import annotations
import pytest
from datetime import datetime
from unittest.mock import patch

from src.kyc.individual.pep_screening import (
    PEPCategory,
    PEPMatch,
    PEPScreeningResult,
    screen_pep,
)


def _make_match(score: float = 90.0) -> PEPMatch:
    return PEPMatch(
        matched_name="Jane Doe",
        category=PEPCategory.SENIOR_OFFICIAL,
        country="GB",
        position="Minister of Finance",
        match_score=score,
        source="Dow Jones",
    )


class TestPEPScreeningResult:
    def test_confirm_pep_sets_edd_required(self, individual_applicant):
        result = PEPScreeningResult(
            applicant_id=individual_applicant.id,
            screened_at=datetime.utcnow(),
            is_pep=False,
            matches=[_make_match(score=70.0)],
        )
        result.confirm_pep(reviewer="compliance_1", notes="Verified via official gazette")
        assert result.is_pep
        assert result.enhanced_due_diligence_required
        assert result.reviewed_by == "compliance_1"

    def test_clear_false_positive_removes_pep_flag(self, individual_applicant):
        result = PEPScreeningResult(
            applicant_id=individual_applicant.id,
            screened_at=datetime.utcnow(),
            is_pep=True,
            matches=[_make_match()],
            enhanced_due_diligence_required=True,
        )
        result.clear_false_positive(reviewer="compliance_1", notes="Different DOB confirmed")
        assert not result.is_pep
        assert result.matches == []
        assert result.reviewed_by == "compliance_1"


class TestScreenPep:
    def test_clean_pass_when_no_matches(self, individual_applicant):
        with patch(
            "src.kyc.individual.pep_screening._query_pep_providers", return_value=[]
        ):
            result = screen_pep(individual_applicant)

        assert not result.is_pep
        assert not result.enhanced_due_diligence_required
        assert result.matches == []

    def test_high_score_match_flags_as_pep(self, individual_applicant):
        match = _make_match(score=90.0)
        with patch(
            "src.kyc.individual.pep_screening._query_pep_providers", return_value=[match]
        ):
            result = screen_pep(individual_applicant)

        assert result.is_pep
        assert result.enhanced_due_diligence_required
        assert len(result.matches) == 1

    def test_below_threshold_score_not_flagged_as_pep(self, individual_applicant):
        # score < 85 should not auto-flag
        match = _make_match(score=80.0)
        with patch(
            "src.kyc.individual.pep_screening._query_pep_providers", return_value=[match]
        ):
            result = screen_pep(individual_applicant)

        assert not result.is_pep
        assert not result.enhanced_due_diligence_required

    def test_pep_threshold_is_85(self, individual_applicant):
        exact = _make_match(score=85.0)
        with patch(
            "src.kyc.individual.pep_screening._query_pep_providers", return_value=[exact]
        ):
            result = screen_pep(individual_applicant)

        assert result.is_pep

    def test_applicant_id_recorded(self, individual_applicant):
        with patch(
            "src.kyc.individual.pep_screening._query_pep_providers", return_value=[]
        ):
            result = screen_pep(individual_applicant)

        assert result.applicant_id == individual_applicant.id
