from __future__ import annotations

from datetime import date

from src.api.rest.extraction import extract_identity_fields


def _mrz_line2(
    passport: str,
    check: str,
    nationality: str,
    dob: str,
    dob_check: str,
    sex: str,
    expiry: str,
    expiry_check: str,
) -> str:
    """Build a 44-char ICAO 9303 type-3 passport MRZ line 2."""
    pad_passport = passport.ljust(9, "<")
    body = (
        f"{pad_passport}{check}{nationality}{dob}{dob_check}{sex}"
        f"{expiry}{expiry_check}{'<' * 14}<0"
    )
    assert len(body) == 44, f"MRZ line 2 must be 44 chars, got {len(body)}"
    return body


def test_parses_clean_passport_mrz() -> None:
    line2 = _mrz_line2("N1234567", "8", "IND", "891104", "0", "F", "341205", "0")
    text = f"P<INDLAUTAVT<<NIDHI<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n{line2}\n"
    result = extract_identity_fields(text)
    assert result.full_name == "Nidhi Lautavt"
    assert result.document_number == "N1234567"
    assert result.date_of_birth == date(1989, 11, 4)
    assert result.expiry_date == date(2034, 12, 5)


def test_mrz_with_surrounding_garbage() -> None:
    """Real OCR output has a lot of noise around the MRZ block."""
    line2 = _mrz_line2("M9876543", "8", "USA", "900115", "0", "M", "350625", "0")
    text = f"""
    REPUBLIC OF INDIA
    Issued at MUMBAI
    P<USASMITH<<JOHN<JANE<<<<<<<<<<<<<<<<<<<<<<<<<<
    {line2}
    Some other text below the MRZ
    """
    result = extract_identity_fields(text)
    assert result.full_name == "John Jane Smith"
    assert result.document_number == "M9876543"


def test_mrz_falls_back_to_label_regex() -> None:
    """When MRZ is absent, the regex extractor still works."""
    text = """Surname / Given Names: ALICE SMITH
Passport No: AB1234567
Date of Birth: 1990-05-01
Date of Expiry: 2030-05-01
"""
    result = extract_identity_fields(text)
    assert result.full_name == "Alice Smith"
    assert result.document_number == "AB1234567"
    assert result.date_of_birth == date(1990, 5, 1)
    assert result.expiry_date == date(2030, 5, 1)


def test_mrz_fills_in_missing_regex_fields() -> None:
    """MRZ + partial regex match → MRZ supplies what regex missed."""
    line2 = _mrz_line2("AB1234567", "8", "GBR", "900501", "0", "F", "300501", "0")
    text = f"P<GBRSMITH<<ALICE<JANE<<<<<<<<<<<<<<<<<<<<<<<<<\n{line2}\n"
    result = extract_identity_fields(text)
    assert result.full_name == "Alice Jane Smith"
    assert result.document_number == "AB1234567"
    assert result.date_of_birth == date(1990, 5, 1)
    assert result.expiry_date == date(2030, 5, 1)


def test_mrz_dob_century_heuristic_for_recent_birthyear() -> None:
    """A YY > today's YY should resolve to the 1900s for DoB."""
    line2 = _mrz_line2("X1111111", "1", "IND", "750101", "0", "M", "300101", "0")
    text = f"P<INDDOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n{line2}\n"
    result = extract_identity_fields(text)
    assert result.date_of_birth == date(1975, 1, 1)


def test_no_mrz_no_labels_returns_empty() -> None:
    text = "this passport scan is incomprehensible to OCR"
    result = extract_identity_fields(text)
    assert result.full_name is None
    assert result.document_number is None
    assert result.date_of_birth is None
    assert result.expiry_date is None
