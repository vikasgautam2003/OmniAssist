from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.artifacts.base import ArtifactStore
from app.tools.artifacts import safe_filename, store
from app.tools.base import ToolContext, ToolError

MAX_BODY = 100_000


class CreateDocument:
    """Writes a PDF the user can download.

    The first tool with a side effect. It is bounded on purpose: it writes only
    to our own artifact store, only for the calling user, and takes no path and
    no URL from the model -- so an instruction injected into an uploaded
    document can at worst cause a pointless PDF to exist.
    """

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    @property
    def name(self) -> str:
        return "create_document"

    @property
    def description(self) -> str:
        return (
            "Write a PDF document and give the user a download link. "
            "Use this when asked to produce a report, summary, letter or any "
            "document as a file. Headings are lines starting with '# '."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "body": {
                    "type": "string",
                    "description": "Body text. Lines starting with '# ' become headings.",
                },
            },
            "required": ["title", "body"],
        }

    def run(self, context: ToolContext, **kwargs: Any) -> str:
        title = kwargs.get("title")
        body = kwargs.get("body")

        if not isinstance(title, str) or not title.strip():
            raise ToolError("a 'title' is required")

        if not isinstance(body, str) or not body.strip():
            raise ToolError("a 'body' is required")

        if len(body) > MAX_BODY:
            raise ToolError(f"body longer than {MAX_BODY} characters is not allowed")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 18)
        # fpdf's core fonts are latin-1 only; a stray em dash would raise.
        # fpdf leaves the cursor at the right margin by default, so the next
        # full-width cell has no room; LMARGIN/NEXT returns it to the left.
        pdf.multi_cell(0, 10, _latin1(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

        for line in body.splitlines():
            if line.startswith("# "):
                pdf.set_font("Helvetica", "B", 13)
                pdf.ln(3)
                pdf.multi_cell(
                    0, 7, _latin1(line[2:]), new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
            elif line.strip():
                pdf.set_font("Helvetica", "", 11)
                pdf.multi_cell(0, 6, _latin1(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.ln(3)

        return store(
            self._artifacts,
            context,
            safe_filename(title, "pdf"),
            "application/pdf",
            bytes(pdf.output()),
        )


def _latin1(text: str) -> str:
    replacements = {
        "—": "-",
        "–": "-",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "…": "...",
        " ": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")
