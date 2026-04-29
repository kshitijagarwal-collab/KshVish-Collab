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


def _autorotate(img):  # type: ignore[no-untyped-def]
    """Detect page rotation via tesseract OSD and apply it.

    Real-world passport scans frequently land upside-down or sideways
    in PDFs — tesseract's OSD detects orientation; we rotate before OCR
    so the text comes out the right way up.
    """
    import pytesseract  # type: ignore[import-untyped]

    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        rotation = int(osd.get("rotate", 0)) % 360
        if rotation:
            img = img.rotate(-rotation, expand=True)
    except Exception:
        pass
    return img


def _ocr_image(payload: bytes) -> Optional[str]:
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image

        with Image.open(io.BytesIO(payload)) as img:
            img.load()
            rotated = _autorotate(img)
            return pytesseract.image_to_string(rotated)
    except Exception as exc:
        logger.warning("tesseract image OCR failed: %s", exc)
        return None


_MRZ_HINT = "P<"


def _ocr_pdf(payload: bytes) -> Optional[str]:
    """OCR a PDF page-by-page, stopping early once we see an MRZ.

    Most passport PDFs have the data page at page 1–3. Once tesseract
    pulls out the MRZ marker, parsing the remaining pages adds latency
    without improving the result. Falls through and OCRs every page if
    no MRZ is detected (multi-page address proofs, etc.).
    """
    try:
        import pytesseract  # type: ignore[import-untyped]
        from pdf2image import convert_from_bytes  # type: ignore[import-untyped]

        pages = convert_from_bytes(payload, dpi=200)
        chunks = []
        for index, page in enumerate(pages):
            rotated = _autorotate(page)
            page_text = pytesseract.image_to_string(rotated)
            chunks.append(page_text)
            if _MRZ_HINT in page_text.upper().replace(" ", ""):
                logger.info(
                    "tesseract: stopping at page %d/%d (MRZ found)",
                    index + 1,
                    len(pages),
                )
                break
        return "\n".join(chunks)
    except Exception as exc:
        logger.warning("tesseract PDF OCR failed: %s", exc)
        return None


def extract_via_tesseract(
    payload: bytes, mime_type: str
) -> Optional[ExtractedDocument]:
    """Run local Tesseract OCR + regex/MRZ extraction on the document.

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
