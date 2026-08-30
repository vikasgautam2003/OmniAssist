from collections.abc import Iterator

from app.clients.base import Message


class FakeLLMClient:
    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message]) -> str:
        self.calls.append(messages)
        return self.reply

    def stream_chat(self, messages: list[Message]) -> Iterator[str]:
        self.calls.append(messages)

        for word in self.reply.split():
            yield word + " "