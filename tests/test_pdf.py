import pytest
from pypdf.errors import PyPdfError

from app.services.pdf import PdfExtractionError, extract_text
from tests.fakes import make_pdf


def test_extracts_the_text_layer() -> None:
    assert "Hello OmniAssist" in extract_text(make_pdf("Hello OmniAssist"))


def test_pages_are_separated() -> None:
    """Page boundaries are real structure and must not be lost."""
    text = extract_text(make_pdf("page one content"))

    assert text.strip() == "page one content"


def test_a_file_that_is_not_a_pdf_is_rejected() -> None:
    with pytest.raises(PdfExtractionError):
        extract_text(b"this is plain text, not a pdf")


def test_an_empty_file_is_rejected() -> None:
    with pytest.raises(PdfExtractionError):
        extract_text(b"")


def test_a_pdf_with_no_text_layer_is_rejected() -> None:
    """A scan has pages but no text. Indexing it silently would leave the
    assistant knowing nothing while the upload appeared to succeed."""
    with pytest.raises(PdfExtractionError, match="OCR"):
        extract_text(make_pdf(""))


def test_pypdf_errors_do_not_escape() -> None:
    """The library must not leak out of this module (C23).

    A caller should never have to import pypdf to handle a bad upload.
    """
    with pytest.raises(PdfExtractionError) as caught:
        extract_text(b"%PDF-1.4 truncated")

    assert not isinstance(caught.value, PyPdfError)
