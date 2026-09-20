from collections.abc import Iterator

from app.clients.base import LLMClient, Message


class ChatService:
    def __init__(self, client: LLMClient, max_history: int = 10) -> None:
        self.client = client
        self._store: dict[str, list[Message]] = {}
        self._max_history = max_history

    def stream_reply(self, conversation_id: str, user_message: str) -> Iterator[str]:

        history = self._store.setdefault(conversation_id, [])

        history.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        trimmed = history[-self._max_history :]

        pieces: list[str] = []

        for chunk in self.client.stream_chat(trimmed):
            pieces.append(chunk)
            yield chunk

        history.append({"role": "assistant", "content": "".join(pieces)})
