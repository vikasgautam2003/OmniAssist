import uuid
from collections.abc import Iterator

from app.clients.base import LLMClient
from app.domain import Chunk, Message
from app.repositories.base import ConversationRepository
from app.services.retrieval import Retriever

GROUNDING = """Answer the question using the passages below when they are relevant.
If the passages do not contain the answer, say so plainly rather than guessing.
Name the document you took an answer from.

Passages:
{passages}"""


def _format_passages(chunks: list[Chunk]) -> str:
    return "\n\n".join(
        f"[{chunk.document_name} #{chunk.chunk_index}]\n{chunk.content}"
        for chunk in chunks
    )


class ChatService:
    def __init__(
        self,
        client: LLMClient,
        repository: ConversationRepository,
        max_history: int = 10,
        retriever: Retriever | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        self._max_history = max_history
        self._retriever = retriever

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

        return self._stream(
            conversation_id, user_id, self._ground(user_id, user_message, trimmed)
        )

    def _ground(
        self, user_id: uuid.UUID, question: str, history: list[Message]
    ) -> list[Message]:
        """Prepend retrieved passages to this one model call.

        The augmented prompt is never stored. History keeps the raw question:
        storing the passages would re-send stale context on every later turn
        and bury what the user actually asked.

        With nothing retrieved the history is returned untouched -- an empty
        context block would make the assistant refuse ordinary questions it
        can answer perfectly well.
        """
        if self._retriever is None:
            return history

        chunks = self._retriever.find(user_id, question)

        if not chunks:
            return history

        grounding: Message = {
            "role": "system",
            "content": GROUNDING.format(passages=_format_passages(chunks)),
        }
        return [grounding, *history]

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
