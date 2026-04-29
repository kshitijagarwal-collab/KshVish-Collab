from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from pypdf import PdfReader

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
)

_NAME_PATTERN = re.compile(
    r"(?i)(?:full\s*name|name|surname\s*/\s*given\s*names?)[:\s]+"
    r"([A-Z][A-Z \-']{2,})",
)
_PASSPORT_PATTERN = re.compile(
    r"(?i)(?:passport\s*(?:no|number|#)|document\s*(?:no|number|#))"
    r"[:\s]*([A-Z]\d{6,8}|[A-Z0-9]{6,12})",
)
_DOB_PATTERN = re.compile(
    r"(?i)(?:date\s*of\s*birth|dob|d\.o\.b\.|birth)\s*[:\s]+"
    r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|"
    r"\d{2}\.\d{2}\.\d{4}|\d{1,2}\s+\w+\s+\d{4})",
)
_EXPIRY_PATTERN = re.compile(
    r"(?i)(?:date\s*of\s*expiry|expiry\s*date|expiration\s*date|expires?|expiry)\s*[:\s]+"
    r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|"
    r"\d{2}\.\d{2}\.\d{4}|\d{1,2}\s+\w+\s+\d{4})",
)

# ICAO 9303 type-3 passport MRZ. Two lines, 44 chars each. Tesseract on
# noisy scans often substitutes 0/O/Q and other lookalikes, so the
# regex tolerates a handful of non-canonical characters and we let the
# parser sanitize.
_MRZ_LINE1 = re.compile(r"^P[<K][A-Z]{3}[A-Z0-9<]{20,}$")
_MRZ_LINE2 = re.compile(r"^[A-Z0-9<]{30,}$")


@dataclass
class ExtractedDocument:
    full_name: Optional[str]
    document_number: Optional[str]
    date_of_birth: Optional[date]
    expiry_date: Optional[date]
    raw_text_length: int

    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "document_number": self.document_number,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
        }


def _parse_date(value: str) -> Optional[date]:
    cleaned = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_mrz_date(yymmdd: str, *, kind: str) -> Optional[date]:
    """Parse a 6-digit MRZ date.

    `kind="dob"` resolves the century relative to today (years > today's
    YY → 19xx, else 20xx). `kind="expiry"` always assumes 20xx since
    passports issued after 2000 won't expire before 2099.
    """
    if not re.fullmatch(r"\d{6}", yymmdd):
        return None
    yy = int(yymmdd[:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])
    if kind == "dob":
        today_yy = date.today().year % 100
        century = 1900 if yy > today_yy else 2000
    else:
        century = 2000
    try:
        return date(century + yy, mm, dd)
    except ValueError:
        return None


def _parse_mrz(text: str) -> Optional[ExtractedDocument]:
    """Look for a passport MRZ in the OCR'd text and parse it.

    MRZ is structured (ICAO 9303) so it gives us name + document number
    + DOB + expiry without relying on label heuristics. Returns None if
    no MRZ pair is found or parsing fails on a critical field.
    """
    cleaned_lines = [
        line.upper().replace(" ", "").strip() for line in text.splitlines()
    ]
    for i, line in enumerate(cleaned_lines):
        if not _MRZ_LINE1.match(line):
            continue
        if i + 1 >= len(cleaned_lines):
            continue
        line2 = cleaned_lines[i + 1]
        if not _MRZ_LINE2.match(line2) or len(line2) < 28:
            continue

        # Line 1: P<COUNTRY<SURNAME<<GIVEN<NAMES<<<<<<...
        name_part = line[5:]
        full_name: Optional[str] = None
        if "<<" in name_part:
            surname_raw, given_raw = name_part.split("<<", 1)
            surname = surname_raw.replace("<", " ").strip().title()
            given = given_raw.rstrip("<").replace("<", " ").strip().title()
            if surname and given:
                full_name = f"{given} {surname}"
            elif surname:
                full_name = surname

        # Line 2 fixed offsets: 0..9 = doc number, 13..19 = DOB, 21..27 = expiry
        document_number_raw = line2[:9].rstrip("<")
        document_number = document_number_raw or None
        dob = _parse_mrz_date(line2[13:19], kind="dob")
        expiry = _parse_mrz_date(line2[21:27], kind="expiry")

        if any([full_name, document_number, dob, expiry]):
            return ExtractedDocument(
                full_name=full_name,
                document_number=document_number,
                date_of_birth=dob,
                expiry_date=expiry,
                raw_text_length=len(text),
            )

    return None


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_identity_fields(text: str) -> ExtractedDocument:
    """Pull identity fields from arbitrary OCR / PDF text.

    Strategy: try the MRZ first (highest signal on passports), then
    fall back to label-based regex. The two paths are merged so MRZ
    fills in fields the regex missed and vice versa.
    """
    mrz_result = _parse_mrz(text)

    name_match = _NAME_PATTERN.search(text)
    passport_match = _PASSPORT_PATTERN.search(text)
    dob_match = _DOB_PATTERN.search(text)
    expiry_match = _EXPIRY_PATTERN.search(text)

    regex_name = (
        " ".join(name_match.group(1).split()).title() if name_match else None
    )
    regex_passport = passport_match.group(1).strip() if passport_match else None
    regex_dob = _parse_date(dob_match.group(1)) if dob_match else None
    regex_expiry = _parse_date(expiry_match.group(1)) if expiry_match else None

    if mrz_result is None:
        return ExtractedDocument(
            full_name=regex_name,
            document_number=regex_passport,
            date_of_birth=regex_dob,
            expiry_date=regex_expiry,
            raw_text_length=len(text),
        )

    return ExtractedDocument(
        full_name=mrz_result.full_name or regex_name,
        document_number=mrz_result.document_number or regex_passport,
        date_of_birth=mrz_result.date_of_birth or regex_dob,
        expiry_date=mrz_result.expiry_date or regex_expiry,
        raw_text_length=len(text),
    )
