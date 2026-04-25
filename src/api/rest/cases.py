from __future__ import annotations
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.case_schemas import (
    ApproveRequest,
    CaseResponse,
    CreateCaseRequest,
    RejectRequest,
    RequestInfoRequest,
)
from src.core.domain.applicant import Address, CorporateApplicant, IndividualApplicant
from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase
from src.core.workflow.state_machine import InvalidTransitionError
from src.infra import store

router = APIRouter(prefix="/cases", tags=["Cases"])


def _case_to_response(case: KYCCase) -> CaseResponse:
    return CaseResponse(
        case_id=case.id,
        status=case.status,
        case_type=case.case_type,
        country_code=case.country_code,
        fund_id=case.fund_id,
        risk_tier=case.risk_tier,
        reviewer_id=case.reviewer_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CaseResponse)
def create_case(body: CreateCaseRequest) -> CaseResponse:
    if body.case_type == CaseType.INDIVIDUAL and not body.individual:
        raise HTTPException(status_code=422, detail="individual applicant data required")
    if body.case_type in (CaseType.CORPORATE, CaseType.INSTITUTIONAL) and not body.corporate:
        raise HTTPException(status_code=422, detail="corporate applicant data required")

    case = KYCCase(
        case_type=body.case_type,
        country_code=body.country_code,
        fund_id=body.fund_id,
    )

    if body.individual:
        ind = body.individual
        applicant = IndividualApplicant(
            first_name=ind.first_name,
            last_name=ind.last_name,
            date_of_birth=ind.date_of_birth,
            nationality=ind.nationality,
            country_of_residence=ind.country_of_residence,
            email=ind.email,
            phone=ind.phone,
            source_of_funds=ind.source_of_funds,
        )
        store.save_applicant(applicant)

    if body.corporate:
        corp = body.corporate
        addr = corp.registered_address
        applicant = CorporateApplicant(
            legal_name=corp.legal_name,
            registration_number=corp.registration_number,
            country_of_incorporation=corp.country_of_incorporation,
            registered_address=Address(
                line1=addr.line1,
                line2=addr.line2,
                city=addr.city,
                state=addr.state,
                postal_code=addr.postal_code,
                country_code=addr.country_code,
            ),
            trading_name=corp.trading_name,
            lei_code=corp.lei_code,
            tax_id=corp.tax_id,
        )
        store.save_applicant(applicant)

    store.save_case(case)
    return _case_to_response(case)


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: UUID) -> CaseResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return _case_to_response(case)


@router.post("/{case_id}/approve", response_model=CaseResponse)
def approve_case(case_id: UUID, body: ApproveRequest) -> CaseResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    try:
        case.transition(CaseStatus.APPROVED, actor=body.reviewer_id, reason="Approved")
        case.reviewer_id = body.reviewer_id
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    store.save_case(case)
    return _case_to_response(case)


@router.post("/{case_id}/reject", response_model=CaseResponse)
def reject_case(case_id: UUID, body: RejectRequest) -> CaseResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    try:
        case.transition(CaseStatus.REJECTED, actor=body.reviewer_id, reason=body.reason)
        case.reviewer_id = body.reviewer_id
        case.rejection_reason = body.reason
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    store.save_case(case)
    return _case_to_response(case)


@router.post("/{case_id}/request-info", response_model=CaseResponse)
def request_info(case_id: UUID, body: RequestInfoRequest) -> CaseResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    try:
        case.transition(CaseStatus.PENDING_INFO, actor=body.reviewer_id, reason=body.reason)
        case.reviewer_id = body.reviewer_id
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    store.save_case(case)
    return _case_to_response(case)
