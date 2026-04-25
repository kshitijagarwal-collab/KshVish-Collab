from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.domain.applicant import IndividualApplicant
from src.core.domain.kyc_case import CaseStatus, CaseType
from src.infra.audit import AuditEvent, AuditEventType, AuditTrail
from src.infra.db import get_session
from src.infra.repositories import (
    CaseRepository,
    DocumentRepository,
    IndividualApplicantRepository,
)
from src.kyc.individual.identity import verify_identity
from src.kyc.individual.pep_screening import screen_pep
from src.kyc.individual.risk_scoring import score_individual
from src.kyc.individual.sanctions import screen_individual

from .schemas import PEPMatchOut, SanctionsHitOut, ScreeningResponse

router = APIRouter(prefix="/cases", tags=["Screening"])


@router.post("/{case_id}/screen", response_model=ScreeningResponse)
def run_screening(
    case_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ScreeningResponse:
    case = CaseRepository(session).get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    if case.case_type != CaseType.INDIVIDUAL:
        raise HTTPException(
            status_code=422, detail="Corporate screening not yet implemented"
        )

    raw_applicant = case.metadata.get("applicant_id")
    if not raw_applicant:
        raise HTTPException(status_code=422, detail="case has no applicant attached")
    applicant: IndividualApplicant | None = IndividualApplicantRepository(session).get(
        UUID(raw_applicant)
    )
    if applicant is None:
        raise HTTPException(status_code=422, detail="applicant not found for case")

    documents = DocumentRepository(session).list_for_case(case_id)

    identity_result = verify_identity(applicant, documents)
    sanctions_result = screen_individual(applicant)
    pep_result = screen_pep(applicant)
    risk_profile = score_individual(applicant, pep_result, sanctions_result)

    case.assign_risk(risk_profile.tier)
    if case.status == CaseStatus.DOCUMENTS_PENDING and identity_result.passed:
        case.transition(CaseStatus.IN_REVIEW, actor="api", reason="screening complete")
    CaseRepository(session).update(case)

    trail = AuditTrail(session=session)
    trail.record(
        AuditEvent(
            event_type=AuditEventType.SANCTIONS_SCREENED,
            case_id=case_id,
            actor="api",
            applicant_id=applicant.id,
            payload={"clear": sanctions_result.is_clear, "hits": len(sanctions_result.hits)},
        )
    )
    trail.record(
        AuditEvent(
            event_type=AuditEventType.PEP_SCREENED,
            case_id=case_id,
            actor="api",
            applicant_id=applicant.id,
            payload={"is_pep": pep_result.is_pep, "matches": len(pep_result.matches)},
        )
    )
    trail.record(
        AuditEvent(
            event_type=AuditEventType.RISK_SCORED,
            case_id=case_id,
            actor="api",
            applicant_id=applicant.id,
            payload={"tier": risk_profile.tier.value, "score": risk_profile.weighted_score},
        )
    )

    session.commit()

    return ScreeningResponse(
        case_id=case_id,
        screened_at=datetime.utcnow(),
        identity_passed=identity_result.passed,
        identity_failure=identity_result.failure_reason,
        sanctions_clear=sanctions_result.is_clear,
        sanctions_hits=[
            SanctionsHitOut(
                list_name=h.list_name.value,
                matched_name=h.matched_name,
                match_score=h.match_score,
                reference=h.reference,
            )
            for h in sanctions_result.hits
        ],
        is_pep=pep_result.is_pep,
        pep_matches=[
            PEPMatchOut(
                matched_name=m.matched_name,
                category=m.category.value,
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
