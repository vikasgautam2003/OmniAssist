from typing import Any, cast

from groq import Groq

from app.clients.base import LLMError, Message


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
            messages=cast(Any, messages),
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content

        if content is None:
            raise LLMError("Provider returned no content")

        return content
