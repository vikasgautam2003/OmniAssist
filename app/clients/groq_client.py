import time
from collections.abc import Iterator, Sequence
from typing import Any, cast

from groq import Groq

from app.clients.base import StreamEvent
from app.domain import Message, ToolCall
from app.observability.logging import get_logger
from app.tools.base import ToolSpec

logger = get_logger("llm")


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
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        cost_per_million_input: float = 0.0,
        cost_per_million_output: float = 0.0,
    ) -> None:
        self.client = Groq(
            api_key=api_key,
            max_retries=2,
        )
        self.model = model
        self.max_tokens = max_tokens
        self._cost_in = cost_per_million_input
        self._cost_out = cost_per_million_output

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

        started = time.perf_counter()
        usage: Any = None

        stream = self.client.chat.completions.create(**request)

        # Providers send tool calls in fragments keyed by index: the id and
        # name arrive first, then the arguments a few characters at a time.
        pending: dict[int, dict[str, str]] = {}

        for chunk in stream:
            if chunk.usage is not None:
                usage = chunk.usage

            if not chunk.choices:
                # The final usage-only chunk carries no choices at all.
                continue

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

        self._log_usage(usage, started, bool(pending), bool(tools))

        if pending:
            # Emitted once, at the end: a half-received call cannot be run.
            yield StreamEvent(
                tool_calls=tuple(
                    ToolCall(**pending[index]) for index in sorted(pending)
                )
            )

    def _log_usage(
        self, usage: Any, started: float, used_tools: bool, offered_tools: bool
    ) -> None:
        # Groq attaches usage to the final chunk of a stream by default.
        # OpenAI requires stream_options={"include_usage": True} for the same
        # thing -- a difference that belongs here, in the adapter, and nowhere
        # above it.
        prompt = getattr(usage, "prompt_tokens", 0) or 0
        completion = getattr(usage, "completion_tokens", 0) or 0
        # Time the request spent waiting at the provider rather than being
        # served. On a free tier this is most of the latency, and it is not
        # something our own code can improve.
        queued_ms = round((getattr(usage, "queue_time", 0.0) or 0.0) * 1000, 1)

        logger.info(
            "llm.call",
            model=self.model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            # Zero on a free tier, but computed the same way: the moment a
            # paid provider is configured these lines become a cost report
            # without anything else changing.
            cost_usd=round(
                prompt / 1_000_000 * self._cost_in
                + completion / 1_000_000 * self._cost_out,
                6,
            ),
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            provider_queue_ms=queued_ms,
            tools_offered=offered_tools,
            tools_requested=used_tools,
        )
