import uuid

import pytest

from app.repositories.base import ConversationNotFoundError
from tests.conftest import ServiceFactory


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
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hi"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hello"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "how are you?"


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
    history.append({"role": "user", "content": "fake message"})

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
