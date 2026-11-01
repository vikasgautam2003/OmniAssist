from collections.abc import Iterator, Sequence
from typing import Any, cast

from groq import Groq

from app.clients.base import StreamEvent
from app.domain import Message, ToolCall
from app.tools.base import ToolSpec


def tool_to_wire(spec: ToolSpec) -> dict[str, Any]:
    """Translate a vendor-neutral ToolSpec into Groq's function-calling shape.

    Anthropic wants {name, description, input_schema} for the same thing. The
    dialect stops here so that swapping provider stays a config change.
    """
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }


def to_wire(message: Message) -> dict[str, Any]:
    """Translate one Message into the shape Groq expects.

    The translation lives here rather than in the domain type because it is
    vendor dialect: Anthropic wants a different shape for the same turn.
    """
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }

    wire: dict[str, Any] = {"role": message.role, "content": message.content}

    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in message.tool_calls
        ]

    return wire


class GroqClient:
    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self.client = Groq(
            api_key=api_key,
            max_retries=2,
        )
        self.model = model
        self.max_tokens = max_tokens

    def stream_chat(
        self, messages: list[Message], tools: Sequence[ToolSpec] = ()
    ) -> Iterator[StreamEvent]:
        """Stream the reply, surfacing tool calls as they finish assembling.

        Streaming and tool use are handled together rather than in two passes.
        The alternative -- run the loop non-streaming, then stream the answer --
        either regenerates the reply at double the cost or fakes the streaming
        of text already in hand. Watching for tool-call deltas costs one
        accumulator and keeps genuine streaming, including the preamble a model
        often emits before calling a tool.
        """
        request: dict[str, Any] = {
            "model": self.model,
            "messages": cast(Any, [to_wire(m) for m in messages]),
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        if tools:
            request["tools"] = [tool_to_wire(spec) for spec in tools]

        stream = self.client.chat.completions.create(**request)

        # Providers send tool calls in fragments keyed by index: the id and
        # name arrive first, then the arguments a few characters at a time.
        pending: dict[int, dict[str, str]] = {}

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                yield StreamEvent(text=delta.content)

            for fragment in delta.tool_calls or []:
                slot = pending.setdefault(
                    fragment.index, {"id": "", "name": "", "arguments": ""}
                )

                if fragment.id:
                    slot["id"] = fragment.id

                if fragment.function:
                    if fragment.function.name:
                        slot["name"] = fragment.function.name
                    if fragment.function.arguments:
                        slot["arguments"] += fragment.function.arguments

        if pending:
            # Emitted once, at the end: a half-received call cannot be run.
            yield StreamEvent(
                tool_calls=tuple(
                    ToolCall(**pending[index]) for index in sorted(pending)
                )
            )
