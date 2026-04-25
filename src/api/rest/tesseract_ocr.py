from __future__ import annotations

import io
import logging
from typing import Optional

from .extraction import ExtractedDocument, extract_identity_fields

logger = logging.getLogger(__name__)


def is_available() -> bool:
    try:
        import pytesseract  # type: ignore[import-untyped]

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_image(payload: bytes) -> Optional[str]:
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image

        with Image.open(io.BytesIO(payload)) as img:
            return pytesseract.image_to_string(img)
    except Exception as exc:
        logger.warning("tesseract image OCR failed: %s", exc)
        return None


def _ocr_pdf(payload: bytes) -> Optional[str]:
    try:
        import pytesseract  # type: ignore[import-untyped]
        from pdf2image import convert_from_bytes  # type: ignore[import-untyped]

        pages = convert_from_bytes(payload, dpi=200)
        return "\n".join(pytesseract.image_to_string(p) for p in pages)
    except Exception as exc:
        logger.warning("tesseract PDF OCR failed: %s", exc)
        return None


def extract_via_tesseract(
    payload: bytes, mime_type: str
) -> Optional[ExtractedDocument]:
    """Run local Tesseract OCR + regex extraction on the document.

    Returns None when tesseract isn't installed, the file format isn't
    something we can rasterize, or OCR raises. Callers treat None as
    "no extraction" and fall back to whatever pypdf produced.
    """
    if not is_available():
        return None

    mt = (mime_type or "").lower()
    is_pdf = mt == "application/pdf"
    is_image = mt.startswith("image/")

    if is_pdf:
        text = _ocr_pdf(payload)
    elif is_image:
        text = _ocr_image(payload)
    else:
        return None

    if not text:
        return None

    return extract_identity_fields(text)
