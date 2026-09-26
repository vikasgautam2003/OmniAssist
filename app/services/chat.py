from collections.abc import Iterator

from app.clients.base import LLMClient, Message
from app.repositories.base import ConversationRepository


class ChatService:
    def __init__(
        self,
        client: LLMClient,
        repository: ConversationRepository,
        max_history: int = 10,
    ) -> None:
        self._client = client
        self._repository = repository
        self._max_history = max_history

    def stream_reply(self, conversation_id: str, user_message: str) -> Iterator[str]:

        self._repository.add_message(
            conversation_id,
            {
                "role": "user",
                "content": user_message,
            },
        )

        trimmed = self._repository.get_history(
            conversation_id,
            limit=self._max_history,
        )

        pieces: list[str] = []

        for chunk in self._client.stream_chat(trimmed):
            pieces.append(chunk)
            yield chunk

        self._repository.add_message(
            conversation_id,
            {
                "role": "assistant",
                "content": "".join(pieces),
            },
        )

    def get_history(self, conversation_id: str) -> list[Message]:
        return self._repository.get_history(conversation_id)
