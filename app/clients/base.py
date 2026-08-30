from collections.abc import Iterator
from typing import Protocol

Message = dict[str, str]


class LLMError(Exception):
    """Raised when an LLM provider fails or returns an unusable response."""


class LLMClient(Protocol):
    def chat(self, messages: list[Message]) -> str: ...

    def stream_chat(self, messages: list[Message]) -> Iterator[str]: ...
