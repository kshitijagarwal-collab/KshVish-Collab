from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.api.schemas.screening_schemas import (
    PEPMatchSchema,
    SanctionsHitSchema,
    ScreeningResponse,
)
from src.core.domain.applicant import IndividualApplicant
from src.core.domain.kyc_case import CaseStatus, CaseType
from src.infra import store
from src.kyc.individual.identity import verify_identity
from src.kyc.individual.pep_screening import screen_pep
from src.kyc.individual.risk_scoring import score_individual
from src.kyc.individual.sanctions import screen_individual

router = APIRouter(prefix="/cases", tags=["Screening"])


@router.post("/{case_id}/screen", response_model=ScreeningResponse)
def run_screening(case_id: UUID) -> ScreeningResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    if case.case_type != CaseType.INDIVIDUAL:
        raise HTTPException(status_code=422, detail="Corporate screening not yet implemented")

    applicant = _get_individual_applicant(case_id)
    if not applicant:
        raise HTTPException(status_code=422, detail="No individual applicant found for this case")

    documents = store.get_documents(case_id)

    identity_result = verify_identity(applicant, documents)
    sanctions_result = screen_individual(applicant)
    pep_result = screen_pep(applicant)
    risk_profile = score_individual(applicant, pep_result, sanctions_result)

    case.assign_risk(risk_profile.tier)
    store.save_case(case)

    return ScreeningResponse(
        case_id=case_id,
        screened_at=datetime.utcnow(),
        identity_passed=identity_result.passed,
        identity_failure=identity_result.failure_reason,
        sanctions_clear=sanctions_result.is_clear,
        sanctions_hits=[
            SanctionsHitSchema(
                list_name=h.list_name,
                matched_name=h.matched_name,
                match_score=h.match_score,
                reference=h.reference,
            )
            for h in sanctions_result.hits
        ],
        is_pep=pep_result.is_pep,
        pep_matches=[
            PEPMatchSchema(
                matched_name=m.matched_name,
                category=m.category,
                country=m.country,
                position=m.position,
                match_score=m.match_score,
            )
            for m in pep_result.matches
        ],
        edd_required=pep_result.enhanced_due_diligence_required,
        risk_tier=risk_profile.tier,
        weighted_score=risk_profile.weighted_score,
    )


def _get_individual_applicant(case_id: UUID) -> IndividualApplicant | None:
    from src.infra.store import _applicants
    for applicant in _applicants.values():
        if isinstance(applicant, IndividualApplicant):
            return applicant
    return None
