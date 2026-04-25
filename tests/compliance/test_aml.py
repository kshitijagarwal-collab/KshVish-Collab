from __future__ import annotations
import pytest
from uuid import uuid4

from src.compliance.aml import (
    AMLFlag,
    AMLFlag_,
    AMLScreeningResult,
    STRStatus,
    SuspiciousTransactionReport,
    run_aml_screening,
)


class TestSuspiciousTransactionReport:
    def test_initial_status_is_draft(self):
        report = SuspiciousTransactionReport(case_id=uuid4(), applicant_id=uuid4())
        assert report.status == STRStatus.DRAFT

    def test_file_sets_status_reference_and_actor(self):
        report = SuspiciousTransactionReport(case_id=uuid4(), applicant_id=uuid4())
        report.file(actor="compliance_1", reference="STR-2026-001")
        assert report.status == STRStatus.FILED
        assert report.filed_by == "compliance_1"
        assert report.regulator_reference == "STR-2026-001"
        assert report.filed_at is not None

    def test_dismiss_sets_status_and_narrative(self):
        report = SuspiciousTransactionReport(case_id=uuid4(), applicant_id=uuid4())
        report.dismiss(reason="False positive after review")
        assert report.status == STRStatus.DISMISSED
        assert "False positive" in report.narrative

    def test_add_flag_appends_to_flags(self):
        report = SuspiciousTransactionReport(case_id=uuid4(), applicant_id=uuid4())
        flag = AMLFlag_(flag_type=AMLFlag.STRUCTURING, description="Multiple small transactions")
        report.add_flag(flag)
        assert len(report.flags) == 1


class TestAMLScreening:
    def test_clean_context_produces_no_flags(self):
        result = run_aml_screening(uuid4(), uuid4(), {"country_code": "GB", "is_pep": False})
        assert result.flag_count() == 0
        assert not result.str_required

    def test_high_risk_jurisdiction_triggers_flag(self):
        result = run_aml_screening(uuid4(), uuid4(), {"country_code": "IR", "is_pep": False})
        assert AMLFlag.HIGH_RISK_JURISDICTION in [f.flag_type for f in result.flags]

    def test_pep_triggers_pep_linked_flag(self):
        result = run_aml_screening(uuid4(), uuid4(), {"country_code": "GB", "is_pep": True})
        assert AMLFlag.PEP_LINKED in [f.flag_type for f in result.flags]

    def test_two_flags_requires_str(self):
        result = run_aml_screening(uuid4(), uuid4(), {"country_code": "IR", "is_pep": True})
        assert result.flag_count() >= 2
        assert result.str_required

    def test_single_flag_does_not_require_str(self):
        result = run_aml_screening(uuid4(), uuid4(), {"country_code": "IR", "is_pep": False})
        assert result.flag_count() == 1
        assert not result.str_required

    def test_result_records_case_and_applicant_ids(self):
        case_id, applicant_id = uuid4(), uuid4()
        result = run_aml_screening(case_id, applicant_id, {})
        assert result.case_id == case_id
        assert result.applicant_id == applicant_id

    def test_unknown_country_does_not_trigger_jurisdiction_flag(self):
        result = run_aml_screening(uuid4(), uuid4(), {"country_code": "XX", "is_pep": False})
        assert AMLFlag.HIGH_RISK_JURISDICTION not in [f.flag_type for f in result.flags]
