from __future__ import annotations

from datetime import date
from unittest.mock import patch

from src.api.rest import tesseract_ocr
from src.api.rest.tesseract_ocr import extract_via_tesseract


def test_returns_none_when_tesseract_missing() -> None:
    with patch.object(tesseract_ocr, "is_available", return_value=False):
        assert extract_via_tesseract(b"\x89PNG-fake", "image/png") is None


def test_returns_none_for_unsupported_mime() -> None:
    with patch.object(tesseract_ocr, "is_available", return_value=True):
        assert extract_via_tesseract(b"data", "application/zip") is None


def test_image_path_runs_image_ocr_and_extracts_fields() -> None:
    fake_text = """
    PASSPORT
    Full Name: ALICE JANE SMITH
    Passport No: AB1234567
    Date of Birth: 1990-05-01
    Date of Expiry: 2030-05-01
    """
    with patch.object(tesseract_ocr, "is_available", return_value=True), patch.object(
        tesseract_ocr, "_ocr_image", return_value=fake_text
    ) as ocr_image, patch.object(tesseract_ocr, "_ocr_pdf") as ocr_pdf:
        result = extract_via_tesseract(b"\x89PNG", "image/png")

    ocr_image.assert_called_once_with(b"\x89PNG")
    ocr_pdf.assert_not_called()
    assert result is not None
    assert result.document_number == "AB1234567"
    assert result.date_of_birth == date(1990, 5, 1)
    assert result.expiry_date == date(2030, 5, 1)


def test_pdf_path_runs_pdf_ocr() -> None:
    fake_text = "Full Name: BOB JONES\nPassport No: X9999999"
    with patch.object(tesseract_ocr, "is_available", return_value=True), patch.object(
        tesseract_ocr, "_ocr_pdf", return_value=fake_text
    ) as ocr_pdf, patch.object(tesseract_ocr, "_ocr_image") as ocr_image:
        result = extract_via_tesseract(b"%PDF-fake", "application/pdf")

    ocr_pdf.assert_called_once_with(b"%PDF-fake")
    ocr_image.assert_not_called()
    assert result is not None
    assert result.document_number == "X9999999"


def test_returns_none_when_ocr_yields_empty_text() -> None:
    with patch.object(tesseract_ocr, "is_available", return_value=True), patch.object(
        tesseract_ocr, "_ocr_image", return_value=""
    ):
        assert extract_via_tesseract(b"\x89PNG", "image/png") is None


def test_returns_none_when_ocr_call_raises() -> None:
    with patch.object(tesseract_ocr, "is_available", return_value=True), patch.object(
        tesseract_ocr, "_ocr_image", return_value=None
    ):
        assert extract_via_tesseract(b"\x89PNG", "image/png") is None
