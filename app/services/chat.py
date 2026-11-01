import uuid
from collections.abc import Generator, Iterator, Sequence

from app.clients.base import LLMClient
from app.domain import Chunk, Message, ToolCall
from app.repositories.base import ConversationRepository
from app.services.retrieval import Retriever
from app.tools.base import ToolSpec
from app.tools.registry import ToolRegistry

NO_MORE_TOOLS = (
    "You have reached the limit on tool calls for this question. "
    "Answer now with what you already know."
)

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
        tools: ToolRegistry | None = None,
        max_tool_iterations: int = 5,
    ) -> None:
        self._client = client
        self._repository = repository
        self._max_history = max_history
        self._retriever = retriever
        self._tools = tools or ToolRegistry()
        self._max_tool_iterations = max_tool_iterations

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
            Message(role="user", content=user_message),
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

        grounding = Message(
            role="system",
            content=GROUNDING.format(passages=_format_passages(chunks)),
        )
        return [grounding, *history]

    def _stream(
        self, conversation_id: str, user_id: uuid.UUID, trimmed: list[Message]
    ) -> Iterator[str]:
        """Stream the reply, running any tools the model asks for.

        Bounded on purpose. A model can keep calling tools -- search, search
        again, search again -- and unbounded that burns the token budget and
        hangs the request with no error at all.
        """
        working = list(trimmed)
        catalogue = self._tools.catalogue()

        for _ in range(self._max_tool_iterations):
            assistant, calls = yield from self._turn(
                conversation_id, user_id, working, catalogue
            )
            working.append(assistant)

            if not calls:
                return

            for call in calls:
                # The registry never raises: a failing tool becomes text the
                # model can read and recover from, not a 500 for the user.
                result = Message(
                    role="tool",
                    content=self._tools.run(call),
                    tool_call_id=call.id,
                )
                self._repository.add_message(conversation_id, user_id, result)
                working.append(result)

        # Out of iterations. Tell the model to stop and answer, so the user
        # gets a reply rather than a request that simply dies.
        working.append(Message(role="system", content=NO_MORE_TOOLS))
        yield from self._turn(conversation_id, user_id, working, ())

    def _turn(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
        working: list[Message],
        catalogue: Sequence[ToolSpec],
    ) -> Generator[str, None, tuple[Message, tuple[ToolCall, ...]]]:
        """One exchange with the model: stream its text, collect its tool calls."""
        pieces: list[str] = []
        calls: tuple[ToolCall, ...] = ()

        for event in self._client.stream_chat(working, tools=catalogue):
            if event.text:
                pieces.append(event.text)
                yield event.text

            if event.tool_calls:
                calls = event.tool_calls

        assistant = Message(role="assistant", content="".join(pieces), tool_calls=calls)
        self._repository.add_message(conversation_id, user_id, assistant)
        return assistant, calls

    def get_history(self, conversation_id: str, user_id: uuid.UUID) -> list[Message]:
        return self._repository.get_history(conversation_id, user_id)
