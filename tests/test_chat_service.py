import uuid

import pytest

from app.domain import Message, ToolCall
from app.repositories.base import ConversationNotFoundError
from app.repositories.memory import InMemoryChunkRepository
from app.services.chat import NO_MORE_TOOLS
from app.services.retrieval import Retriever
from app.tools.calculator import Calculator
from app.tools.registry import ToolRegistry
from tests.conftest import ServiceFactory
from tests.fakes import FakeEmbedder


def test_reply_is_streamed_back(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, _fake = make_service("Hello there?")

    reply = "".join(service.stream_reply("c1", user_id, "hi"))

    assert reply == "Hello there?"


def test_history_accumulates_across_turns(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, fake = make_service("hello")

    "".join(service.stream_reply("c1", user_id, "hi"))
    "".join(service.stream_reply("c1", user_id, "how are you?"))

    messages = fake.calls[-1]

    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[0].content == "hi"
    assert messages[1].role == "assistant"
    assert messages[1].content == "hello"
    assert messages[2].role == "user"
    assert messages[2].content == "how are you?"


def test_trimming_limits_what_is_sent(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, fake = make_service("reply", max_history=4)

    for i in range(6):
        "".join(service.stream_reply("c1", user_id, f"message {i}"))

    assert len(fake.calls[-1]) <= 4


def test_full_history_is_retained_while_trimming(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, _fake = make_service("reply", max_history=4)

    for i in range(6):
        "".join(service.stream_reply("c1", user_id, f"message {i}"))

    assert len(service.get_history("c1", user_id)) == 12


def test_get_history_returns_a_copy(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, _fake = make_service("reply")

    "".join(service.stream_reply("c1", user_id, "hello"))

    history = service.get_history("c1", user_id)
    history.append(Message(role="user", content="fake message"))

    assert len(service.get_history("c1", user_id)) == 2


def test_another_users_conversation_is_invisible(
    make_service: ServiceFactory, user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    """Reading someone else's conversation must look like it does not exist."""
    service, _fake = make_service("reply")

    "".join(service.stream_reply("shared-id", user_id, "my secret is 1234"))

    assert service.get_history("shared-id", other_user_id) == []


def test_writing_to_another_users_conversation_is_rejected(
    make_service: ServiceFactory, user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    """Guessing a conversation id must not grant write access to it."""
    service, _fake = make_service("reply")

    "".join(service.stream_reply("shared-id", user_id, "my secret is 1234"))

    with pytest.raises(ConversationNotFoundError):
        "".join(service.stream_reply("shared-id", other_user_id, "what is it?"))


def test_ownership_is_checked_before_the_stream_is_consumed(
    make_service: ServiceFactory, user_id: uuid.UUID, other_user_id: uuid.UUID
) -> None:
    """The rejection must happen on call, not on first iteration.

    stream_reply used to be a generator, so the ownership check only ran once
    the response was already being streamed — too late for the route to return
    a 404.
    """
    service, _fake = make_service("reply")

    "".join(service.stream_reply("shared-id", user_id, "my secret is 1234"))

    with pytest.raises(ConversationNotFoundError):
        service.stream_reply("shared-id", other_user_id, "what is it?")


def _retriever(user_id: uuid.UUID, texts: list[str], document: str = "policy.pdf"):
    embedder = FakeEmbedder()
    chunks = InMemoryChunkRepository()
    chunks.add(
        user_id=user_id,
        document_name=document,
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )
    return Retriever(embedder, chunks)


def test_retrieved_passages_reach_the_model(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    retriever = _retriever(user_id, ["the refund window is 30 days"])
    service, fake = make_service(retriever=retriever)

    "".join(service.stream_reply("c1", user_id, "the refund window is 30 days"))

    sent = fake.calls[0]
    assert sent[0].role == "system"
    assert "the refund window is 30 days" in sent[0].content
    assert "policy.pdf" in sent[0].content


def test_history_stores_the_raw_question_not_the_augmented_prompt(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    """Storing the passages would re-send stale context every later turn and
    bury what the user actually asked."""
    retriever = _retriever(user_id, ["the refund window is 30 days"])
    service, _ = make_service(retriever=retriever)

    "".join(service.stream_reply("c1", user_id, "how long for a refund?"))

    stored = service.get_history("c1", user_id)
    assert stored[0] == Message(role="user", content="how long for a refund?")
    assert all("Passages:" not in message.content for message in stored)


def test_the_grounding_instruction_is_sent(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    retriever = _retriever(user_id, ["anything"])
    service, fake = make_service(retriever=retriever)

    "".join(service.stream_reply("c1", user_id, "anything"))

    assert "say so plainly rather than guessing" in fake.calls[0][0].content


def test_no_retriever_means_no_context_block(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, fake = make_service()

    "".join(service.stream_reply("c1", user_id, "hello"))

    assert all(message.role != "system" for message in fake.calls[0])


def test_nothing_retrieved_leaves_the_prompt_alone(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    """An empty context block would make the assistant refuse ordinary
    questions it can answer perfectly well."""
    retriever = _retriever(uuid.uuid4(), ["someone else's document"])
    service, fake = make_service(retriever=retriever)

    "".join(service.stream_reply("c1", user_id, "what is the capital of France?"))

    assert all(message.role != "system" for message in fake.calls[0])


def _calc_registry() -> ToolRegistry:
    return ToolRegistry([Calculator()])


def _call(
    name: str = "calculate", arguments: str = '{"expression": "6*7"}'
) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


def test_a_tool_the_model_asks_for_is_run_and_fed_back(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, fake = make_service(
        reply="42", tools=_calc_registry(), tool_calls=[[_call()]]
    )

    "".join(service.stream_reply("c1", user_id, "what is 6 times 7?"))

    second_turn = fake.calls[1]
    assert second_turn[-1].role == "tool"
    assert second_turn[-1].content == "42"
    assert second_turn[-1].tool_call_id == "c1"


def test_the_catalogue_is_offered_to_the_model(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, fake = make_service(tools=_calc_registry())

    "".join(service.stream_reply("c1", user_id, "hello"))

    assert [spec.name for spec in fake.tools_offered[0]] == ["calculate"]


def test_no_tools_means_no_catalogue(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    service, fake = make_service()

    "".join(service.stream_reply("c1", user_id, "hello"))

    assert fake.tools_offered[0] == []


def test_the_tool_turn_is_stored_in_history(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    """A tool call is a turn in the conversation, not a separate store."""
    service, _ = make_service(
        reply="42", tools=_calc_registry(), tool_calls=[[_call()]]
    )

    "".join(service.stream_reply("c1", user_id, "what is 6 times 7?"))

    roles = [m.role for m in service.get_history("c1", user_id)]
    assert roles == ["user", "assistant", "tool", "assistant"]


def test_a_failing_tool_does_not_fail_the_request(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    """The error becomes text the model can read, not a 500 for the user."""
    service, fake = make_service(
        reply="I cannot divide by zero.",
        tools=_calc_registry(),
        tool_calls=[[_call(arguments='{"expression": "1/0"}')]],
    )

    reply = "".join(service.stream_reply("c1", user_id, "what is 1/0?"))

    assert reply == "I cannot divide by zero."
    assert "zero" in fake.calls[1][-1].content


def test_the_loop_is_bounded(make_service: ServiceFactory, user_id: uuid.UUID) -> None:
    """A model that keeps calling tools would otherwise burn the token budget
    and hang the request with no error at all."""
    forever = [[_call()] for _ in range(50)]
    service, fake = make_service(
        reply="done",
        tools=_calc_registry(),
        tool_calls=forever,
        max_tool_iterations=3,
    )

    "".join(service.stream_reply("c1", user_id, "loop please"))

    assert len(fake.calls) == 4, "three tool turns, then one final answer"
    assert NO_MORE_TOOLS in fake.calls[-1][-1].content


def test_text_before_a_tool_call_still_streams(
    make_service: ServiceFactory, user_id: uuid.UUID
) -> None:
    """Models often say 'let me check that' before calling a tool. Streaming
    and tool detection happen together so the preamble is not swallowed."""
    service, _ = make_service(
        reply="The answer is 42.", tools=_calc_registry(), tool_calls=[[_call()]]
    )

    reply = "".join(service.stream_reply("c1", user_id, "what is 6 times 7?"))

    assert reply == "The answer is 42."
