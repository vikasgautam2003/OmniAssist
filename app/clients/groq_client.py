from collections.abc import Iterator
from typing import Any, cast

from groq import Groq

from app.clients.base import LLMError
from app.domain import Message


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

    def chat(self, messages: list[Message]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, [to_wire(m) for m in messages]),
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content

        if content is None:
            raise LLMError("Provider returned no content")

        return content

    def stream_chat(self, messages: list[Message]) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, [to_wire(m) for m in messages]),
            max_tokens=self.max_tokens,
            stream=True,
        )

        for chunk in stream:
            content = chunk.choices[0].delta.content

            if content is not None:
                yield content
