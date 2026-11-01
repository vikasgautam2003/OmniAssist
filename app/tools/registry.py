import json
import time
from collections.abc import Iterator, Sequence

from app.domain import ToolCall
from app.observability.logging import get_logger
from app.tools.base import Tool, ToolContext, ToolError, ToolSpec

logger = get_logger("tools")


class ToolRegistry:
    """Holds the tools the model may call, and runs the ones it asks for."""

    def __init__(self, tools: Sequence[Tool] = ()) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def catalogue(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
            for tool in self._tools.values()
        ]

    def run(self, call: ToolCall, context: ToolContext) -> str:
        """Run one tool call and return what the model should see.

        Never raises. Every failure becomes text fed back to the model, which
        can then correct itself or tell the user -- a tool that cannot divide
        by zero is not a reason to fail the whole request.
        """
        tool = self._tools.get(call.name)

        if tool is None:
            # The model invented a name. Saying so is more useful than silence:
            # it can pick a real one on the next turn.
            return f"No tool named {call.name!r} exists."

        try:
            arguments = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            return f"The arguments for {call.name!r} were not valid JSON."

        if not isinstance(arguments, dict):
            return f"The arguments for {call.name!r} must be a JSON object."

        started = time.perf_counter()

        try:
            result = tool.run(context, **arguments)
        except ToolError as exc:
            self._log(call.name, started, "failed", str(exc))
            return f"{call.name} failed: {exc}"
        except TypeError as exc:
            self._log(call.name, started, "bad_arguments", str(exc))
            # Wrong or missing arguments despite the schema. The model is an
            # untrusted caller; the schema constrains shape, not correctness.
            return f"{call.name} was called with the wrong arguments: {exc}"

        self._log(call.name, started, "ok")
        return result

    def _log(
        self, name: str, started: float, outcome: str, detail: str | None = None
    ) -> None:
        # Arguments are deliberately not logged: a model composes them from
        # document text, which may be the user's private data.
        logger.info(
            "tool.call",
            tool=name,
            outcome=outcome,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            detail=detail,
        )
