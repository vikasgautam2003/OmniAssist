import re
from typing import Any

from app.artifacts.base import ArtifactStore
from app.tools.base import ToolContext, ToolError

MAX_ROWS = 2000
MAX_CELL = 500


def safe_filename(name: str, extension: str) -> str:
    """Reduce a model-supplied name to something safe to send as a filename.

    The model composed this string, and it reaches a Content-Disposition
    header: a newline there is header injection, and '../' would be path
    traversal if files were ever written to disk. Whitelisting is the defence,
    for the same reason it is in the calculator -- the set of dangerous inputs
    is unbounded, the set of safe characters is not.
    """
    # Models often include the extension in the title. Stripping the dot first
    # and appending afterwards would turn "Report.xlsx" into "Reportxlsx.xlsx".
    stem = re.sub(rf"\.{extension}$", "", (name or "").strip(), flags=re.IGNORECASE)
    stem = re.sub(r"[^A-Za-z0-9 _-]", "", stem).strip() or "document"
    return f"{stem[:60]}.{extension}"


def store(
    artifacts: ArtifactStore,
    context: ToolContext,
    filename: str,
    media_type: str,
    content: bytes,
) -> str:
    """Save a generated file and describe it the way the model should see it.

    The bytes never enter the conversation. A base64 payload would be sent back
    to the model on every later turn, filling the context window with data it
    cannot read and paying for the tokens each time.
    """
    artifact_id = artifacts.save(context.scope, filename, media_type, content)
    return (
        f"Created {filename} ({len(content) // 1024 or 1} KB). "
        f"Download it at /artifacts/{artifact_id}"
    )


def rows_from(value: Any, what: str) -> list[list[str]]:
    """Validate a table the model composed, and normalise it to strings."""
    if not isinstance(value, list) or not value:
        raise ToolError(f"{what} must be a non-empty list of rows")

    if len(value) > MAX_ROWS:
        raise ToolError(f"{what} has more than {MAX_ROWS} rows")

    rows: list[list[str]] = []

    for row in value:
        if not isinstance(row, list):
            raise ToolError(f"every row in {what} must itself be a list")
        rows.append([str(cell)[:MAX_CELL] for cell in row])

    return rows
