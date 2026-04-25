from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.domain.applicant import (
    Address,
    CorporateApplicant,
    IndividualApplicant,
)
from src.core.domain.kyc_case import CaseType, KYCCase
from src.infra.audit import AuditEvent, AuditEventType, AuditTrail
from src.infra.db import get_session
from src.infra.repositories import (
    CaseRepository,
    CorporateApplicantRepository,
    IndividualApplicantRepository,
)

from .schemas import CaseResponse, CreateCaseRequest

router = APIRouter(prefix="/cases", tags=["Cases"])


def _case_to_response(case: KYCCase) -> CaseResponse:
    raw_applicant = case.metadata.get("applicant_id")
    return CaseResponse(
        case_id=case.id,
        case_type=case.case_type,
        status=case.status,
        country_code=case.country_code,
        fund_id=case.fund_id,
        risk_tier=case.risk_tier,
        reviewer_id=case.reviewer_id,
        rejection_reason=case.rejection_reason,
        applicant_id=UUID(raw_applicant) if raw_applicant else None,
        applicant_name=case.metadata.get("applicant_name"),
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CaseResponse)
def create_case(
    body: CreateCaseRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CaseResponse:
    if body.case_type == CaseType.INDIVIDUAL and body.individual is None:
        raise HTTPException(
            status_code=422, detail="individual applicant data required"
        )
    if (
        body.case_type in (CaseType.CORPORATE, CaseType.INSTITUTIONAL)
        and body.corporate is None
    ):
        raise HTTPException(
            status_code=422, detail="corporate applicant data required"
        )

    case = KYCCase(
        case_type=body.case_type,
        country_code=body.country_code.upper(),
        fund_id=body.fund_id,
    )

    applicant_id: Optional[UUID]
    if body.individual is not None:
        ind = body.individual
        addr = (
            Address(
                line1=ind.address.line1,
                city=ind.address.city,
                country_code=ind.address.country_code.upper(),
                postal_code=ind.address.postal_code,
                line2=ind.address.line2,
                state=ind.address.state,
            )
            if ind.address is not None
            else None
        )
        applicant = IndividualApplicant(
            first_name=ind.first_name,
            last_name=ind.last_name,
            date_of_birth=ind.date_of_birth,
            nationality=ind.nationality.upper(),
            country_of_residence=ind.country_of_residence.upper(),
            email=str(ind.email),
            middle_name=ind.middle_name,
            phone=ind.phone,
            address=addr,
            investor_class=ind.investor_class,
            tax_id=ind.tax_id,
            source_of_funds=ind.source_of_funds,
        )
        IndividualApplicantRepository(session).add(applicant)
        applicant_id = applicant.id
        applicant_name: str = applicant.full_name
    else:
        assert body.corporate is not None
        corp = body.corporate
        addr_corp = Address(
            line1=corp.registered_address.line1,
            city=corp.registered_address.city,
            country_code=corp.registered_address.country_code.upper(),
            postal_code=corp.registered_address.postal_code,
            line2=corp.registered_address.line2,
            state=corp.registered_address.state,
        )
        corporate = CorporateApplicant(
            legal_name=corp.legal_name,
            registration_number=corp.registration_number,
            country_of_incorporation=corp.country_of_incorporation.upper(),
            registered_address=addr_corp,
            trading_name=corp.trading_name,
            incorporation_date=corp.incorporation_date,
            business_type=corp.business_type,
            regulated=corp.regulated,
            regulator=corp.regulator,
            lei_code=corp.lei_code,
            tax_id=corp.tax_id,
        )
        CorporateApplicantRepository(session).add(corporate)
        applicant_id = corporate.id
        applicant_name = corporate.legal_name

    case.metadata["applicant_id"] = str(applicant_id)
    case.metadata["applicant_name"] = applicant_name
    CaseRepository(session).add(case)

    AuditTrail(session=session).record(
        AuditEvent(
            event_type=AuditEventType.CASE_CREATED,
            case_id=case.id,
            actor="api",
            applicant_id=applicant_id,
            payload={
                "case_type": case.case_type.value,
                "country_code": case.country_code,
                "fund_id": case.fund_id,
            },
        )
    )

    session.commit()
    return _case_to_response(case)


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> CaseResponse:
    case = CaseRepository(session).get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return _case_to_response(case)
