from __future__ import annotations
import pytest
from datetime import date
from uuid import uuid4

from src.core.domain.document import Document, DocumentStatus, DocumentType
from src.kyc.individual.identity import verify_identity


def _make_doc(
    applicant_id,
    doc_type=DocumentType.PASSPORT,
    status=DocumentStatus.VERIFIED,
    expiry_date=date(2030, 1, 1),
) -> Document:
    return Document(
        case_id=uuid4(),
        applicant_id=applicant_id,
        doc_type=doc_type,
        file_name="doc.pdf",
        storage_ref="s3://kyc/test/doc",
        status=status,
        expiry_date=expiry_date,
    )


class TestVerifyIdentity:
    def test_no_documents_fails(self, individual_applicant):
        result = verify_identity(individual_applicant, documents=[])
        assert not result.passed
        assert "No identity document" in result.failure_reason

    def test_non_identity_doc_type_ignored(self, individual_applicant):
        # PROOF_OF_ADDRESS is not an identity doc
        doc = _make_doc(individual_applicant.id, doc_type=DocumentType.PROOF_OF_ADDRESS)
        result = verify_identity(individual_applicant, documents=[doc])
        assert not result.passed
        assert "No identity document" in result.failure_reason

    def test_uploaded_but_unverified_doc_fails(self, individual_applicant):
        doc = _make_doc(individual_applicant.id, status=DocumentStatus.UPLOADED)
        result = verify_identity(individual_applicant, documents=[doc])
        assert not result.passed
        assert "not yet verified" in result.failure_reason

    def test_under_review_doc_fails(self, individual_applicant):
        doc = _make_doc(individual_applicant.id, status=DocumentStatus.UNDER_REVIEW)
        result = verify_identity(individual_applicant, documents=[doc])
        assert not result.passed

    def test_expired_verified_doc_fails(self, individual_applicant):
        doc = _make_doc(
            individual_applicant.id,
            status=DocumentStatus.VERIFIED,
            expiry_date=date(2000, 1, 1),
        )
        result = verify_identity(individual_applicant, documents=[doc])
        assert not result.passed
        assert "expired" in result.failure_reason

    def test_valid_passport_passes(self, individual_applicant, verified_passport):
        result = verify_identity(individual_applicant, documents=[verified_passport])
        assert result.passed
        assert result.document_id == verified_passport.id
        assert result.doc_type == DocumentType.PASSPORT

    def test_all_identity_doc_types_accepted(self, individual_applicant):
        for doc_type in [
            DocumentType.PASSPORT,
            DocumentType.NATIONAL_ID,
            DocumentType.DRIVING_LICENCE,
        ]:
            doc = _make_doc(individual_applicant.id, doc_type=doc_type)
            result = verify_identity(individual_applicant, documents=[doc])
            assert result.passed, f"Expected {doc_type} to pass identity verification"

    def test_doc_for_different_applicant_ignored(self, individual_applicant):
        other_id = uuid4()
        doc = _make_doc(other_id)  # different applicant
        result = verify_identity(individual_applicant, documents=[doc])
        assert not result.passed

    def test_prefers_first_valid_doc(self, individual_applicant):
        doc1 = _make_doc(individual_applicant.id, doc_type=DocumentType.PASSPORT)
        doc2 = _make_doc(individual_applicant.id, doc_type=DocumentType.NATIONAL_ID)
        result = verify_identity(individual_applicant, documents=[doc1, doc2])
        assert result.passed
        assert result.document_id == doc1.id
