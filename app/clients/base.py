from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain import Message, ToolCall
from app.tools.base import ToolSpec


class LLMError(Exception):
    """Raised when an LLM provider fails or returns an unusable response."""


@dataclass(frozen=True)
class StreamEvent:
    """One thing that came back from the model.

    Text arrives in many small events; tool calls arrive as a single event once
    the provider has finished assembling them, because a half-received call
    cannot be run.
    """

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


class LLMClient(Protocol):
    def stream_chat(
        self, messages: list[Message], tools: Sequence[ToolSpec] = ()
    ) -> Iterator[StreamEvent]: ...
