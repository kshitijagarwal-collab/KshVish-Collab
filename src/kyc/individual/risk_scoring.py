from __future__ import annotations
from uuid import UUID

from src.core.domain.applicant import IndividualApplicant
from src.core.domain.risk_profile import RiskFactor, RiskProfile
from src.kyc.individual.pep_screening import PEPScreeningResult
from src.kyc.individual.sanctions import SanctionsScreeningResult


# Scoring weights — calibrated to FATF risk-based approach
WEIGHT_COUNTRY_RISK = 0.30
WEIGHT_PEP = 0.25
WEIGHT_SANCTIONS = 0.30
WEIGHT_SOURCE_OF_FUNDS = 0.15

HIGH_RISK_COUNTRIES = {"IR", "KP", "MM", "SY", "YE", "AF", "LY", "SO"}
MEDIUM_RISK_COUNTRIES = {"RU", "PK", "NG", "KE", "VN", "TH", "UA"}


def score_individual(
    applicant: IndividualApplicant,
    pep_result: PEPScreeningResult,
    sanctions_result: SanctionsScreeningResult,
) -> RiskProfile:
    profile = RiskProfile(
        case_id=UUID(int=0),
        applicant_id=applicant.id,
    )

    profile.add_factor(_score_country_risk(applicant))
    profile.add_factor(_score_pep(pep_result))
    profile.add_factor(_score_sanctions(sanctions_result))
    profile.add_factor(_score_source_of_funds(applicant))

    return profile


def _score_country_risk(applicant: IndividualApplicant) -> RiskFactor:
    country = applicant.country_of_residence
    if country in HIGH_RISK_COUNTRIES:
        score, reason = 90.0, f"{country} is FATF high-risk/sanctioned jurisdiction"
    elif country in MEDIUM_RISK_COUNTRIES:
        score, reason = 50.0, f"{country} is elevated-risk jurisdiction"
    else:
        score, reason = 10.0, "Standard jurisdiction"

    return RiskFactor(
        name="country_risk",
        score=score,
        weight=WEIGHT_COUNTRY_RISK,
        reason=reason,
    )


def _score_pep(result: PEPScreeningResult) -> RiskFactor:
    if result.is_pep:
        score = 85.0
        reason = f"Confirmed PEP: {', '.join(m.position for m in result.matches)}"
    else:
        score = 0.0
        reason = "No PEP match"

    return RiskFactor(name="pep", score=score, weight=WEIGHT_PEP, reason=reason)


def _score_sanctions(result: SanctionsScreeningResult) -> RiskFactor:
    if result.has_confirmed_hit():
        score = 100.0
        reason = f"Sanctions hit on {', '.join(h.list_name for h in result.hits)}"
    else:
        score = 0.0
        reason = "No sanctions match"

    return RiskFactor(name="sanctions", score=score, weight=WEIGHT_SANCTIONS, reason=reason)


def _score_source_of_funds(applicant: IndividualApplicant) -> RiskFactor:
    if not applicant.source_of_funds:
        return RiskFactor(
            name="source_of_funds",
            score=40.0,
            weight=WEIGHT_SOURCE_OF_FUNDS,
            reason="Source of funds not declared",
        )
    return RiskFactor(
        name="source_of_funds",
        score=5.0,
        weight=WEIGHT_SOURCE_OF_FUNDS,
        reason="Source of funds declared",
    )
