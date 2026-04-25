from __future__ import annotations
import pytest

from src.compliance.rule_engine import (
    Rule,
    RuleEngine,
    RuleEngineResult,
    RuleOutcome,
    RuleResult,
)


def _pass_rule(rule_id: str = "RULE-001", countries: list = None, case_types: list = None) -> Rule:
    return Rule(
        id=rule_id,
        name="Always Pass",
        description="Test rule that always passes",
        evaluate=lambda ctx: RuleOutcome(rule_id=rule_id, result=RuleResult.PASS, message="OK"),
        countries=countries or [],
        case_types=case_types or [],
    )


def _fail_rule(rule_id: str = "RULE-002") -> Rule:
    return Rule(
        id=rule_id,
        name="Always Fail",
        description="Test rule that always fails",
        evaluate=lambda ctx: RuleOutcome(rule_id=rule_id, result=RuleResult.FAIL, message="Failed"),
    )


def _warn_rule(rule_id: str = "RULE-003") -> Rule:
    return Rule(
        id=rule_id,
        name="Always Warn",
        description="Test rule that always warns",
        evaluate=lambda ctx: RuleOutcome(rule_id=rule_id, result=RuleResult.WARN, message="Warning"),
    )


def _error_rule(rule_id: str = "RULE-ERR") -> Rule:
    def bad_evaluate(ctx):
        raise ValueError("Unexpected error")
    return Rule(id=rule_id, name="Error Rule", description="Raises", evaluate=bad_evaluate)


class TestRuleEngineBasics:
    def setup_method(self):
        self.engine = RuleEngine()

    def test_empty_engine_returns_passed_result(self):
        result = self.engine.evaluate({}, "GB", "INDIVIDUAL")
        assert result.passed
        assert result.outcomes == []

    def test_pass_rule_produces_pass_outcome(self):
        self.engine.register(_pass_rule())
        result = self.engine.evaluate({}, "GB", "INDIVIDUAL")
        assert result.passed
        assert result.outcomes[0].result == RuleResult.PASS

    def test_fail_rule_produces_failed_result(self):
        self.engine.register(_fail_rule())
        result = self.engine.evaluate({}, "GB", "INDIVIDUAL")
        assert not result.passed
        assert len(result.failures) == 1

    def test_warn_rule_does_not_fail_result(self):
        self.engine.register(_warn_rule())
        result = self.engine.evaluate({}, "GB", "INDIVIDUAL")
        assert result.passed
        assert len(result.warnings) == 1

    def test_mixed_rules_fail_on_any_failure(self):
        self.engine.register(_pass_rule("R1"))
        self.engine.register(_fail_rule("R2"))
        self.engine.register(_warn_rule("R3"))
        result = self.engine.evaluate({}, "GB", "INDIVIDUAL")
        assert not result.passed

    def test_exception_in_rule_converts_to_fail(self):
        self.engine.register(_error_rule())
        result = self.engine.evaluate({}, "GB", "INDIVIDUAL")
        assert not result.passed
        assert "Rule evaluation error" in result.failures[0].message


class TestRuleFiltering:
    def setup_method(self):
        self.engine = RuleEngine()

    def test_country_specific_rule_only_applies_to_its_country(self):
        rule = Rule(
            id="AE-ONLY",
            name="AE Rule",
            description="Only for AE",
            evaluate=lambda ctx: RuleOutcome(rule_id="AE-ONLY", result=RuleResult.FAIL, message="AE fail"),
            countries=["AE"],
        )
        self.engine.register(rule)
        assert self.engine.evaluate({}, "GB", "INDIVIDUAL").passed
        assert not self.engine.evaluate({}, "AE", "INDIVIDUAL").passed

    def test_case_type_specific_rule_only_applies_to_its_type(self):
        rule = Rule(
            id="CORP-ONLY",
            name="Corporate Rule",
            description="Only for CORPORATE",
            evaluate=lambda ctx: RuleOutcome(rule_id="CORP-ONLY", result=RuleResult.FAIL, message="Corp fail"),
            case_types=["CORPORATE"],
        )
        self.engine.register(rule)
        assert self.engine.evaluate({}, "GB", "INDIVIDUAL").passed
        assert not self.engine.evaluate({}, "GB", "CORPORATE").passed

    def test_rule_with_no_filters_applies_to_all(self):
        self.engine.register(_fail_rule())
        for country, case_type in [("GB", "INDIVIDUAL"), ("AE", "CORPORATE"), ("US", "INSTITUTIONAL")]:
            assert not self.engine.evaluate({}, country, case_type).passed

    def test_applies_to_respects_combined_country_and_type_filter(self):
        rule = Rule(
            id="MULTI",
            name="Multi",
            description="Multi filter",
            evaluate=lambda ctx: RuleOutcome(rule_id="MULTI", result=RuleResult.PASS, message="OK"),
            countries=["GB", "US"],
            case_types=["INDIVIDUAL"],
        )
        assert rule.applies_to("GB", "INDIVIDUAL")
        assert rule.applies_to("US", "INDIVIDUAL")
        assert not rule.applies_to("AE", "INDIVIDUAL")
        assert not rule.applies_to("GB", "CORPORATE")


class TestRuleEngineResult:
    def test_failures_property_filters_only_fail_outcomes(self):
        result = RuleEngineResult(country="GB", case_type="INDIVIDUAL", outcomes=[
            RuleOutcome(rule_id="R1", result=RuleResult.PASS, message="OK"),
            RuleOutcome(rule_id="R2", result=RuleResult.FAIL, message="Fail"),
            RuleOutcome(rule_id="R3", result=RuleResult.WARN, message="Warn"),
        ])
        assert len(result.failures) == 1
        assert result.failures[0].rule_id == "R2"

    def test_warnings_property_filters_only_warn_outcomes(self):
        result = RuleEngineResult(country="GB", case_type="INDIVIDUAL", outcomes=[
            RuleOutcome(rule_id="R1", result=RuleResult.PASS, message="OK"),
            RuleOutcome(rule_id="R2", result=RuleResult.WARN, message="Warn"),
        ])
        assert len(result.warnings) == 1

    def test_passed_is_true_with_only_warns(self):
        result = RuleEngineResult(country="GB", case_type="INDIVIDUAL", outcomes=[
            RuleOutcome(rule_id="R1", result=RuleResult.WARN, message="Warn"),
        ])
        assert result.passed
