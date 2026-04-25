from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from pypdf import PdfReader

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y")

_NAME_PATTERN = re.compile(
    r"(?i)(?:full\s*name|name|surname\s*/\s*given\s*names?)[:\s]+"
    r"([A-Z][A-Z\s\-']{2,})",
)
_PASSPORT_PATTERN = re.compile(
    r"(?i)(?:passport\s*(?:no|number|#)|document\s*(?:no|number|#))"
    r"[:\s]*([A-Z0-9]{6,12})",
)
_DOB_PATTERN = re.compile(
    r"(?i)(?:date\s*of\s*birth|dob|d\.o\.b\.)\s*[:\s]+"
    r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|\d{1,2}\s+\w+\s+\d{4})",
)
_EXPIRY_PATTERN = re.compile(
    r"(?i)(?:date\s*of\s*expiry|expiry\s*date|expiration\s*date|expires?)\s*[:\s]+"
    r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|\d{1,2}\s+\w+\s+\d{4})",
)


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
    from datetime import datetime as dt

    cleaned = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_identity_fields(text: str) -> ExtractedDocument:
    name_match = _NAME_PATTERN.search(text)
    passport_match = _PASSPORT_PATTERN.search(text)
    dob_match = _DOB_PATTERN.search(text)
    expiry_match = _EXPIRY_PATTERN.search(text)

    full_name = " ".join(name_match.group(1).split()).title() if name_match else None
    return ExtractedDocument(
        full_name=full_name,
        document_number=passport_match.group(1).strip() if passport_match else None,
        date_of_birth=_parse_date(dob_match.group(1)) if dob_match else None,
        expiry_date=_parse_date(expiry_match.group(1)) if expiry_match else None,
        raw_text_length=len(text),
    )
