from io import BytesIO
from typing import Any

import matplotlib

# Chosen before pyplot is imported. The default backend wants a window system,
# which a server does not have -- without this the first call would hang or
# crash depending on the host.
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.artifacts.base import ArtifactStore
from app.tools.artifacts import safe_filename, store
from app.tools.base import ToolContext, ToolError

KINDS = ("bar", "line", "pie")
MAX_POINTS = 200


class CreateChart:
    """Draws a chart the user can download."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    @property
    def name(self) -> str:
        return "create_chart"

    @property
    def description(self) -> str:
        return (
            "Draw a bar, line or pie chart from labelled values and give the "
            "user a download link. Use this when asked to plot, chart, graph "
            "or visualise numbers."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Chart title"},
                "kind": {"type": "string", "enum": list(KINDS)},
                "labels": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["title", "kind", "labels", "values"],
        }

    def run(self, context: ToolContext, **kwargs: Any) -> str:
        title = kwargs.get("title")
        kind = kwargs.get("kind")
        labels = kwargs.get("labels")
        values = kwargs.get("values")

        if not isinstance(title, str) or not title.strip():
            raise ToolError("a 'title' is required")

        if kind not in KINDS:
            raise ToolError(f"'kind' must be one of {', '.join(KINDS)}")

        if not isinstance(labels, list) or not isinstance(values, list):
            raise ToolError("'labels' and 'values' must both be lists")

        if len(labels) != len(values):
            raise ToolError(
                f"got {len(labels)} labels and {len(values)} values; "
                "they must correspond one to one"
            )

        if not labels:
            raise ToolError("there is nothing to plot")

        if len(labels) > MAX_POINTS:
            raise ToolError(f"more than {MAX_POINTS} points is not supported")

        numbers = [_as_number(value) for value in values]
        names = [str(label)[:40] for label in labels]

        figure, axes = plt.subplots(figsize=(8, 4.5))
        try:
            if kind == "bar":
                axes.bar(names, numbers, color="#7C6CFF")
                axes.tick_params(axis="x", labelrotation=30)
            elif kind == "line":
                axes.plot(names, numbers, marker="o", color="#7C6CFF")
                axes.tick_params(axis="x", labelrotation=30)
            else:
                if any(number < 0 for number in numbers):
                    raise ToolError("a pie chart cannot show negative values")
                axes.pie(numbers, labels=names, autopct="%1.1f%%")

            axes.set_title(title)
            figure.tight_layout()

            buffer = BytesIO()
            figure.savefig(buffer, format="png", dpi=150)
        finally:
            # Figures are not garbage collected while pyplot holds them; a
            # server drawing charts all day would leak until it died.
            plt.close(figure)

        return store(
            self._artifacts,
            context,
            safe_filename(title, "png"),
            "image/png",
            buffer.getvalue(),
        )


def _as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"{value!r} is not a number") from exc
