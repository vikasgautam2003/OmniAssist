import uuid

import pytest
from openpyxl import load_workbook

from app.artifacts.memory import InMemoryArtifactStore
from app.domain import Artifact
from app.tools.base import ToolContext, ToolError
from app.tools.charts import CreateChart
from app.tools.documents import CreateDocument
from app.tools.spreadsheets import CreateSpreadsheet


@pytest.fixture
def store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(user_id=uuid.uuid4())


def only_artifact(store: InMemoryArtifactStore) -> Artifact:
    return next(iter(store._rows.values()))[1]


# ---------------------------------------------------------------- documents
def test_a_pdf_is_produced(store: InMemoryArtifactStore, context: ToolContext) -> None:
    result = CreateDocument(store).run(context, title="Report", body="Hello")

    assert "Download it at /artifacts/" in result
    assert only_artifact(store).content.startswith(b"%PDF-")


def test_the_bytes_never_enter_the_conversation(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """A base64 payload would be re-sent to the model on every later turn,
    filling the context window with data it cannot read."""
    result = CreateDocument(store).run(context, title="Report", body="Hello")

    assert len(result) < 200
    assert "%PDF" not in result


def test_a_filename_cannot_escape_or_inject(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """The model composed this string and it reaches a Content-Disposition
    header, where a newline is header injection."""
    CreateDocument(store).run(context, title="../../etc/passwd\r\nX-Evil: 1", body="x")

    name = only_artifact(store).filename
    assert "/" not in name and "\r" not in name and "\n" not in name


def test_unicode_punctuation_does_not_crash_the_pdf(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """fpdf's core fonts are latin-1; an em dash from a model would raise."""
    CreateDocument(store).run(context, title="Q3 — Summary", body="“quoted”")

    assert only_artifact(store).content.startswith(b"%PDF-")


def test_an_empty_document_is_refused(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    with pytest.raises(ToolError):
        CreateDocument(store).run(context, title="", body="x")


# ---------------------------------------------------------------- spreadsheets
def test_a_spreadsheet_is_produced(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    CreateSpreadsheet(store).run(
        context, title="Sales", rows=[["Month", "Revenue"], ["Jan", "120"]]
    )
    artifact = only_artifact(store)

    assert artifact.filename == "Sales.xlsx"
    assert artifact.content[:2] == b"PK"  # xlsx is a zip


def test_a_formula_is_written_as_text(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """A spreadsheet formula is executable. A model composing a cell from
    document text could produce one by accident."""
    from io import BytesIO

    CreateSpreadsheet(store).run(
        context, title="Sheet", rows=[["a"], ["=1+1"], ["@SUM(A1)"]]
    )
    sheet = load_workbook(BytesIO(only_artifact(store).content)).active
    assert sheet is not None

    assert sheet["A2"].value == "'=1+1"
    assert sheet["A3"].value == "'@SUM(A1)"


def test_rows_must_be_lists(store: InMemoryArtifactStore, context: ToolContext) -> None:
    with pytest.raises(ToolError, match="list"):
        CreateSpreadsheet(store).run(context, title="x", rows=["not a row"])


def test_an_empty_spreadsheet_is_refused(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    with pytest.raises(ToolError):
        CreateSpreadsheet(store).run(context, title="x", rows=[])


# ---------------------------------------------------------------- charts
@pytest.mark.parametrize("kind", ["bar", "line", "pie"])
def test_each_chart_kind_is_produced(
    store: InMemoryArtifactStore, context: ToolContext, kind: str
) -> None:
    CreateChart(store).run(
        context, title="Revenue", kind=kind, labels=["a", "b"], values=[1, 2]
    )

    assert only_artifact(store).content.startswith(b"\x89PNG")


def test_mismatched_labels_and_values_are_refused(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """Pairing label 3 with value 4 would produce a chart that is confidently
    wrong, which is worse than one that fails."""
    with pytest.raises(ToolError, match="one to one"):
        CreateChart(store).run(
            context, title="x", kind="bar", labels=["a", "b"], values=[1]
        )


def test_an_unknown_chart_kind_is_refused(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    with pytest.raises(ToolError, match="kind"):
        CreateChart(store).run(
            context, title="x", kind="sunburst", labels=["a"], values=[1]
        )


def test_a_pie_chart_refuses_negative_values(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    with pytest.raises(ToolError, match="negative"):
        CreateChart(store).run(
            context, title="x", kind="pie", labels=["a", "b"], values=[1, -2]
        )


def test_non_numeric_values_are_refused(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    with pytest.raises(ToolError, match="not a number"):
        CreateChart(store).run(
            context, title="x", kind="bar", labels=["a"], values=["banana"]
        )


def test_figures_do_not_leak(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """pyplot holds every figure until closed; a server drawing charts all day
    would leak until it died."""
    import matplotlib.pyplot as plt

    for _ in range(12):
        CreateChart(store).run(context, title="x", kind="bar", labels=["a"], values=[1])

    assert plt.get_fignums() == []


# ---------------------------------------------------------------- ownership
def test_another_user_cannot_fetch_an_artifact(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    CreateDocument(store).run(context, title="Private", body="secret")
    artifact_id = next(iter(store._rows))

    assert store.get(uuid.uuid4(), artifact_id) is None
    assert store.get(context.user_id, artifact_id) is not None


def test_a_title_that_already_has_the_extension_is_not_doubled(
    store: InMemoryArtifactStore, context: ToolContext
) -> None:
    """Models routinely pass "Report.xlsx" as the title."""
    CreateSpreadsheet(store).run(context, title="Sales.xlsx", rows=[["a"]])

    assert only_artifact(store).filename == "Sales.xlsx"
