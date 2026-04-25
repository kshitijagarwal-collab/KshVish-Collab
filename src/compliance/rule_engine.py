from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class RuleResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class RuleOutcome:
    rule_id: str
    result: RuleResult
    message: str
    severity: str = "INFO"
    remediation: Optional[str] = None


@dataclass
class Rule:
    id: str
    name: str
    description: str
    evaluate: Callable[[dict], RuleOutcome]
    countries: list[str] = field(default_factory=list)
    case_types: list[str] = field(default_factory=list)
    severity: str = "ERROR"

    def applies_to(self, country: str, case_type: str) -> bool:
        country_match = not self.countries or country in self.countries
        type_match = not self.case_types or case_type in self.case_types
        return country_match and type_match


@dataclass
class RuleEngineResult:
    country: str
    case_type: str
    outcomes: list[RuleOutcome] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(o.result != RuleResult.FAIL for o in self.outcomes)

    @property
    def failures(self) -> list[RuleOutcome]:
        return [o for o in self.outcomes if o.result == RuleResult.FAIL]

    @property
    def warnings(self) -> list[RuleOutcome]:
        return [o for o in self.outcomes if o.result == RuleResult.WARN]


class RuleEngine:
    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        self._rules.append(rule)

    def evaluate(self, context: dict[str, Any], country: str, case_type: str) -> RuleEngineResult:
        result = RuleEngineResult(country=country, case_type=case_type)

        applicable = [r for r in self._rules if r.applies_to(country, case_type)]
        for rule in applicable:
            try:
                outcome = rule.evaluate(context)
            except Exception as exc:
                outcome = RuleOutcome(
                    rule_id=rule.id,
                    result=RuleResult.FAIL,
                    message=f"Rule evaluation error: {exc}",
                    severity="CRITICAL",
                )
            result.outcomes.append(outcome)

        return result


_engine = RuleEngine()


def get_engine() -> RuleEngine:
    return _engine


def register_rule(rule: Rule) -> None:
    _engine.register(rule)
