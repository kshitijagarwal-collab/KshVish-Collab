from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.core.domain.applicant import (
    Address,
    CorporateApplicant,
    IndividualApplicant,
    InvestorClass,
)
from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.core.domain.kyc_case import CaseStatus, CaseType, KYCCase, RiskTier
from src.infra.orm import (
    Base,
    CorporateApplicantORM,
    DocumentORM,
    IndividualApplicantORM,
    KYCCaseORM,
)


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _ts() -> datetime:
    return datetime(2026, 4, 25, 12, 0, 0)


def test_kyc_case_round_trip(session: Session) -> None:
    case = KYCCase(
        case_type=CaseType.INDIVIDUAL,
        country_code="GB",
        fund_id="FUND-001",
        status=CaseStatus.IN_REVIEW,
        risk_tier=RiskTier.MEDIUM,
        created_at=_ts(),
        updated_at=_ts(),
        reviewer_id="reviewer-1",
        expiry_date=datetime(2027, 1, 1),
        metadata={"note": "imported"},
    )
    session.add(KYCCaseORM.from_domain(case))
    session.commit()

    fetched = session.get(KYCCaseORM, str(case.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == case


def test_kyc_case_minimal_defaults(session: Session) -> None:
    case = KYCCase(
        case_type=CaseType.CORPORATE,
        country_code="DE",
        fund_id="FUND-002",
        created_at=_ts(),
        updated_at=_ts(),
    )
    session.add(KYCCaseORM.from_domain(case))
    session.commit()

    fetched = session.get(KYCCaseORM, str(case.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == case
    assert restored.status == CaseStatus.INITIATED
    assert restored.risk_tier is None
    assert restored.metadata == {}


def test_kyc_case_metadata_persists_nested_structures(session: Session) -> None:
    case = KYCCase(
        case_type=CaseType.INSTITUTIONAL,
        country_code="US",
        fund_id="FUND-003",
        created_at=_ts(),
        updated_at=_ts(),
        metadata={"tier": "EDD", "flags": ["pep", "high-risk"], "score": 87},
    )
    session.add(KYCCaseORM.from_domain(case))
    session.commit()

    fetched = session.get(KYCCaseORM, str(case.id))
    assert fetched is not None
    assert fetched.case_metadata == {
        "tier": "EDD",
        "flags": ["pep", "high-risk"],
        "score": 87,
    }


def test_document_round_trip(session: Session) -> None:
    case_id = uuid4()
    parent = KYCCase(
        case_type=CaseType.INDIVIDUAL,
        country_code="GB",
        fund_id="FUND-001",
        id=case_id,
        created_at=_ts(),
        updated_at=_ts(),
    )
    session.add(KYCCaseORM.from_domain(parent))
    session.commit()

    doc = Document(
        case_id=case_id,
        applicant_id=uuid4(),
        doc_type=DocumentType.PASSPORT,
        file_name="passport.pdf",
        storage_ref="s3://bucket/abc",
        status=DocumentStatus.VERIFIED,
        uploaded_at=_ts(),
        verified_at=_ts(),
        expiry_date=date(2030, 1, 1),
        country_of_issue="GB",
        document_number="X12345",
        mime_type="application/pdf",
    )
    session.add(DocumentORM.from_domain(doc))
    session.commit()

    fetched = session.get(DocumentORM, str(doc.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == doc


def test_document_minimal_uploaded_state(session: Session) -> None:
    case_id = uuid4()
    parent = KYCCase(
        case_type=CaseType.INDIVIDUAL,
        country_code="US",
        fund_id="FUND-002",
        id=case_id,
        created_at=_ts(),
        updated_at=_ts(),
    )
    session.add(KYCCaseORM.from_domain(parent))
    session.commit()

    doc = Document(
        case_id=case_id,
        applicant_id=uuid4(),
        doc_type=DocumentType.UTILITY_BILL,
        file_name="bill.pdf",
        storage_ref="s3://bucket/bill",
        uploaded_at=_ts(),
    )
    session.add(DocumentORM.from_domain(doc))
    session.commit()

    fetched = session.get(DocumentORM, str(doc.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == doc
    assert restored.status == DocumentStatus.UPLOADED
    assert restored.verified_at is None
    assert restored.expiry_date is None


def test_individual_applicant_round_trip_with_address(session: Session) -> None:
    applicant = IndividualApplicant(
        first_name="Alice",
        last_name="Smith",
        date_of_birth=date(1990, 5, 1),
        nationality="GB",
        country_of_residence="GB",
        email="alice@example.com",
        middle_name="Jane",
        phone="+44 20 0000 0000",
        address=Address(
            line1="221B Baker Street",
            city="London",
            country_code="GB",
            postal_code="NW1 6XE",
            line2="Flat 2",
            state="Greater London",
        ),
        investor_class=InvestorClass.PROFESSIONAL,
        is_pep=False,
        is_sanctioned=False,
        tax_id="GB123456",
        source_of_funds="Salary",
    )
    session.add(IndividualApplicantORM.from_domain(applicant))
    session.commit()

    fetched = session.get(IndividualApplicantORM, str(applicant.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == applicant


def test_individual_applicant_round_trip_without_address(session: Session) -> None:
    applicant = IndividualApplicant(
        first_name="Bob",
        last_name="Jones",
        date_of_birth=date(1985, 3, 15),
        nationality="US",
        country_of_residence="US",
        email="bob@example.com",
    )
    session.add(IndividualApplicantORM.from_domain(applicant))
    session.commit()

    fetched = session.get(IndividualApplicantORM, str(applicant.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == applicant
    assert restored.address is None


def test_individual_applicant_pep_and_sanctioned_flags_round_trip(
    session: Session,
) -> None:
    applicant = IndividualApplicant(
        first_name="Carol",
        last_name="Lee",
        date_of_birth=date(1975, 7, 12),
        nationality="SG",
        country_of_residence="SG",
        email="carol@example.com",
        is_pep=True,
        is_sanctioned=True,
    )
    session.add(IndividualApplicantORM.from_domain(applicant))
    session.commit()

    fetched = session.get(IndividualApplicantORM, str(applicant.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored.is_pep is True
    assert restored.is_sanctioned is True
    assert restored.is_high_risk()


def test_corporate_applicant_round_trip(session: Session) -> None:
    applicant = CorporateApplicant(
        legal_name="Acme Holdings Ltd",
        registration_number="0123456",
        country_of_incorporation="GB",
        registered_address=Address(
            line1="1 Cheapside",
            city="London",
            country_code="GB",
            postal_code="EC2V 6DN",
        ),
        trading_name="Acme",
        incorporation_date=date(2010, 6, 1),
        business_type="Asset Management",
        regulated=True,
        regulator="FCA",
        lei_code="529900T8BM49AURSDO55",
        tax_id="GB987654",
        ubo_complete=True,
    )
    session.add(CorporateApplicantORM.from_domain(applicant))
    session.commit()

    fetched = session.get(CorporateApplicantORM, str(applicant.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == applicant


def test_corporate_applicant_minimal(session: Session) -> None:
    applicant = CorporateApplicant(
        legal_name="Tiny Co",
        registration_number="999",
        country_of_incorporation="KY",
        registered_address=Address(
            line1="PO Box 1",
            city="Grand Cayman",
            country_code="KY",
            postal_code="KY1-1000",
        ),
    )
    session.add(CorporateApplicantORM.from_domain(applicant))
    session.commit()

    fetched = session.get(CorporateApplicantORM, str(applicant.id))
    assert fetched is not None
    restored = fetched.to_domain()
    assert restored == applicant
    assert restored.regulated is False
    assert restored.ubo_complete is False
