from __future__ import annotations

from datetime import date

from src.api.rest.extraction import extract_identity_fields


def test_extracts_full_name() -> None:
    text = "Full Name: ALICE SMITH"
    result = extract_identity_fields(text)
    assert result.full_name == "Alice Smith"


def test_extracts_passport_number() -> None:
    text = "Passport No: AB1234567"
    result = extract_identity_fields(text)
    assert result.document_number == "AB1234567"


def test_extracts_date_of_birth_iso() -> None:
    text = "Date of Birth: 1990-05-01"
    result = extract_identity_fields(text)
    assert result.date_of_birth == date(1990, 5, 1)


def test_extracts_date_of_birth_dmy_slash() -> None:
    text = "DOB: 01/05/1990"
    result = extract_identity_fields(text)
    assert result.date_of_birth == date(1990, 5, 1)


def test_extracts_expiry_date() -> None:
    text = "Date of Expiry: 2030-01-01"
    result = extract_identity_fields(text)
    assert result.expiry_date == date(2030, 1, 1)


def test_extracts_all_fields_from_passport_like_text() -> None:
    text = """
    BRITISH PASSPORT
    Surname / Given Names: ALICE JANE SMITH
    Passport No: AB1234567
    Date of Birth: 1990-05-01
    Date of Expiry: 2030-05-01
    """
    result = extract_identity_fields(text)
    assert result.document_number == "AB1234567"
    assert result.date_of_birth == date(1990, 5, 1)
    assert result.expiry_date == date(2030, 5, 1)


def test_returns_none_when_no_matches() -> None:
    result = extract_identity_fields("just some random text without identity fields")
    assert result.full_name is None
    assert result.document_number is None
    assert result.date_of_birth is None
    assert result.expiry_date is None
