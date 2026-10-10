from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError


class PdfExtractionError(Exception):
    """Raised when a file cannot be read as a PDF, or carries no text."""


def extract_text(data: bytes) -> str:
    """Extract the text layer of a PDF."""
    try:
        reader = PdfReader(BytesIO(data))

        if reader.is_encrypted:
            raise PdfExtractionError("This PDF is password protected.")

        pages = [page.extract_text() or "" for page in reader.pages]
    except PyPdfError as exc:
        raise PdfExtractionError("This file could not be read as a PDF.") from exc

    text = "\n\n".join(pages).strip()

    if not text:
        raise PdfExtractionError(
            "No text could be extracted. If this is a scanned document, it "
            "needs OCR first."
        )

    return text
