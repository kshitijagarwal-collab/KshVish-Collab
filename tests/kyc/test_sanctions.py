from __future__ import annotations
import pytest
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from src.core.domain.applicant import IndividualApplicant
from src.kyc.individual.sanctions import (
    SanctionsHit,
    SanctionsList,
    SanctionsScreeningResult,
    screen_individual,
)


def _make_hit(list_name: SanctionsList = SanctionsList.OFAC_SDN) -> SanctionsHit:
    return SanctionsHit(
        list_name=list_name,
        matched_name="Jane Doe",
        match_score=95.0,
        reference="SDN-12345",
        details="Designated individual",
    )


class TestSanctionsScreeningResult:
    def test_clear_result_has_no_confirmed_hit(self, individual_applicant):
        result = SanctionsScreeningResult(
            applicant_id=individual_applicant.id,
            screened_at=datetime.utcnow(),
            is_clear=True,
        )
        assert not result.has_confirmed_hit()

    def test_hit_result_has_confirmed_hit(self, individual_applicant):
        result = SanctionsScreeningResult(
            applicant_id=individual_applicant.id,
            screened_at=datetime.utcnow(),
            is_clear=False,
            hits=[_make_hit()],
        )
        assert result.has_confirmed_hit()

    def test_false_positive_clears_confirmed_hit(self, individual_applicant):
        result = SanctionsScreeningResult(
            applicant_id=individual_applicant.id,
            screened_at=datetime.utcnow(),
            is_clear=False,
            hits=[_make_hit()],
        )
        result.clear_as_false_positive(actor="reviewer_1", reason="Name collision — different DOB")
        assert not result.has_confirmed_hit()
        assert result.false_positive_cleared
        assert result.cleared_by == "reviewer_1"

    def test_false_positive_records_reason(self, individual_applicant):
        result = SanctionsScreeningResult(
            applicant_id=individual_applicant.id,
            screened_at=datetime.utcnow(),
            is_clear=False,
            hits=[_make_hit()],
        )
        result.clear_as_false_positive(actor="reviewer_1", reason="Different nationality")
        assert result.cleared_reason == "Different nationality"


class TestScreenIndividual:
    def test_clean_pass_when_no_provider_hits(self, individual_applicant):
        with patch(
            "src.kyc.individual.sanctions._query_sanctions_providers", return_value=[]
        ):
            result = screen_individual(individual_applicant)

        assert result.is_clear
        assert result.hits == []
        assert result.applicant_id == individual_applicant.id

    def test_all_lists_checked_by_default(self, individual_applicant):
        with patch(
            "src.kyc.individual.sanctions._query_sanctions_providers", return_value=[]
        ):
            result = screen_individual(individual_applicant)

        assert set(result.lists_checked) == set(SanctionsList)

    def test_specific_lists_can_be_requested(self, individual_applicant):
        lists = [SanctionsList.OFAC_SDN, SanctionsList.UN_CONSOLIDATED]
        with patch(
            "src.kyc.individual.sanctions._query_sanctions_providers", return_value=[]
        ):
            result = screen_individual(individual_applicant, lists=lists)

        assert result.lists_checked == lists

    def test_confirmed_hit_when_provider_returns_match(self, individual_applicant):
        hit = _make_hit(SanctionsList.OFAC_SDN)
        with patch(
            "src.kyc.individual.sanctions._query_sanctions_providers", return_value=[hit]
        ):
            result = screen_individual(individual_applicant)

        assert not result.is_clear
        assert result.has_confirmed_hit()
        assert len(result.hits) == 1
        assert result.hits[0].list_name == SanctionsList.OFAC_SDN

    def test_multiple_list_hits_all_recorded(self, individual_applicant):
        hits = [_make_hit(SanctionsList.OFAC_SDN), _make_hit(SanctionsList.EU_CONSOLIDATED)]
        with patch(
            "src.kyc.individual.sanctions._query_sanctions_providers", return_value=hits
        ):
            result = screen_individual(individual_applicant)

        assert len(result.hits) == 2
