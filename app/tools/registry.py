import json
from collections.abc import Iterator, Sequence

from app.domain import ToolCall
from app.tools.base import Tool, ToolError, ToolSpec


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

    def run(self, call: ToolCall) -> str:
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

        try:
            return tool.run(**arguments)
        except ToolError as exc:
            return f"{call.name} failed: {exc}"
        except TypeError as exc:
            # Wrong or missing arguments despite the schema. The model is an
            # untrusted caller; the schema constrains shape, not correctness.
            return f"{call.name} was called with the wrong arguments: {exc}"
