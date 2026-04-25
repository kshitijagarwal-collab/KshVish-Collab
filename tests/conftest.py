from __future__ import annotations
import pytest
from datetime import date, datetime
from uuid import uuid4

from src.core.domain.applicant import IndividualApplicant, CorporateApplicant, Address
from src.core.domain.document import Document, DocumentType, DocumentStatus
from src.core.domain.kyc_case import KYCCase, CaseStatus, CaseType, RiskTier
from src.kyc.individual.pep_screening import PEPScreeningResult
from src.kyc.individual.sanctions import SanctionsScreeningResult, SanctionsList


@pytest.fixture
def individual_applicant() -> IndividualApplicant:
    return IndividualApplicant(
        first_name="Jane",
        last_name="Doe",
        date_of_birth=date(1985, 6, 15),
        nationality="GB",
        country_of_residence="GB",
        email="jane.doe@example.com",
        source_of_funds="Salary",
    )


@pytest.fixture
def high_risk_applicant() -> IndividualApplicant:
    return IndividualApplicant(
        first_name="Ali",
        last_name="Hassan",
        date_of_birth=date(1975, 3, 10),
        nationality="IR",
        country_of_residence="IR",
        email="ali.hassan@example.com",
    )


@pytest.fixture
def corporate_applicant() -> CorporateApplicant:
    return CorporateApplicant(
        legal_name="Acme Holdings Ltd",
        registration_number="12345678",
        country_of_incorporation="GB",
        registered_address=Address(
            line1="1 Finance Street",
            city="London",
            country_code="GB",
            postal_code="EC1A 1BB",
        ),
    )


@pytest.fixture
def verified_passport(individual_applicant: IndividualApplicant) -> Document:
    doc = Document(
        case_id=uuid4(),
        applicant_id=individual_applicant.id,
        doc_type=DocumentType.PASSPORT,
        file_name="passport.pdf",
        storage_ref="s3://kyc/passports/abc123",
        expiry_date=date(2030, 1, 1),
        status=DocumentStatus.VERIFIED,
    )
    return doc


@pytest.fixture
def clean_sanctions_result(individual_applicant: IndividualApplicant) -> SanctionsScreeningResult:
    return SanctionsScreeningResult(
        applicant_id=individual_applicant.id,
        screened_at=datetime.utcnow(),
        is_clear=True,
        lists_checked=list(SanctionsList),
    )


@pytest.fixture
def clean_pep_result(individual_applicant: IndividualApplicant) -> PEPScreeningResult:
    return PEPScreeningResult(
        applicant_id=individual_applicant.id,
        screened_at=datetime.utcnow(),
        is_pep=False,
    )


@pytest.fixture
def initiated_case(individual_applicant: IndividualApplicant) -> KYCCase:
    return KYCCase(
        case_type=CaseType.INDIVIDUAL,
        country_code="GB",
        fund_id="FUND-001",
    )
