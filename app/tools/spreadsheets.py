from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.artifacts.base import ArtifactStore
from app.tools.artifacts import rows_from, safe_filename, store
from app.tools.base import ToolContext, ToolError

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CreateSpreadsheet:
    """Writes an .xlsx the user can download."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    @property
    def name(self) -> str:
        return "create_spreadsheet"

    @property
    def description(self) -> str:
        return (
            "Write tabular data to an Excel spreadsheet and give the user a "
            "download link. Use this when asked for a table, a list of records, "
            "or data as a file. The first row is treated as the header."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "File name"},
                "rows": {
                    "type": "array",
                    "description": "Rows of cells; the first row is the header.",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
            },
            "required": ["title", "rows"],
        }

    def run(self, context: ToolContext, **kwargs: Any) -> str:
        title = kwargs.get("title")

        if not isinstance(title, str) or not title.strip():
            raise ToolError("a 'title' is required")

        rows = rows_from(kwargs.get("rows"), "rows")

        workbook = Workbook()
        sheet = workbook.active

        if sheet is None:  # pragma: no cover - openpyxl always makes one
            raise ToolError("could not create the spreadsheet")

        for row in rows:
            # openpyxl treats a leading '=' as a formula. A model composing a
            # cell from document text could produce one by accident, and a
            # spreadsheet formula is executable -- so cells are written as text.
            sheet.append([_as_text(cell) for cell in row])

        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for index, column in enumerate(zip(*rows, strict=False), start=1):
            widest = max((len(value) for value in column), default=10)
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(widest + 2, 10), 60
            )

        buffer = BytesIO()
        workbook.save(buffer)

        return store(
            self._artifacts,
            context,
            safe_filename(title, "xlsx"),
            XLSX_MEDIA_TYPE,
            buffer.getvalue(),
        )


def _as_text(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value
