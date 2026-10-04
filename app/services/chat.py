import uuid
from collections.abc import Iterator

from app.clients.base import LLMClient
from app.domain import Message
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

    def stream_reply(
        self, conversation_id: str, user_id: uuid.UUID, user_message: str
    ) -> Iterator[str]:
        """Record the user's message and return a stream of the reply.

        Deliberately not a generator. The ownership check inside add_message
        must run when this is *called*, not when the result is first iterated:
        by then the response headers are already on the wire and the route can
        no longer turn a rejection into a 404.
        """
        self._repository.add_message(
            conversation_id,
            user_id,
            {"role": "user", "content": user_message},
        )

        trimmed = self._repository.get_history(
            conversation_id,
            user_id,
            limit=self._max_history,
        )

        return self._stream(conversation_id, user_id, trimmed)

    def _stream(
        self, conversation_id: str, user_id: uuid.UUID, trimmed: list[Message]
    ) -> Iterator[str]:
        pieces: list[str] = []

        for chunk in self._client.stream_chat(trimmed):
            pieces.append(chunk)
            yield chunk

        self._repository.add_message(
            conversation_id,
            user_id,
            {"role": "assistant", "content": "".join(pieces)},
        )

    def get_history(self, conversation_id: str, user_id: uuid.UUID) -> list[Message]:
        return self._repository.get_history(conversation_id, user_id)
