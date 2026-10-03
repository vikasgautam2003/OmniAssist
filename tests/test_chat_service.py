from tests.conftest import ServiceFactory


def test_reply_is_streamed_back(make_service: ServiceFactory) -> None:
    service, _fake = make_service("Hello there?")

    reply = "".join(service.stream_reply("c1", "hi"))

    assert reply == "Hello there?"


def test_history_accumulates_across_turns(make_service: ServiceFactory) -> None:
    service, fake = make_service("hello")

    "".join(service.stream_reply("c1", "hi"))
    "".join(service.stream_reply("c1", "how are you?"))

    messages = fake.calls[-1]

    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hi"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hello"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "how are you?"


def test_trimming_limits_what_is_sent(make_service: ServiceFactory) -> None:
    service, fake = make_service("reply", max_history=4)

    for i in range(6):
        "".join(service.stream_reply("c1", f"message {i}"))

    messages = fake.calls[-1]

    assert len(messages) <= 4


def test_full_history_is_retained_while_trimming(make_service: ServiceFactory) -> None:
    service, _fake = make_service("reply", max_history=4)

    for i in range(6):
        "".join(service.stream_reply("c1", f"message {i}"))

    history = service.get_history("c1")

    assert len(history) == 12


def test_get_history_returns_a_copy(make_service: ServiceFactory) -> None:
    service, _fake = make_service("reply")

    "".join(service.stream_reply("c1", "hello"))

    history = service.get_history("c1")
    history.append({"role": "user", "content": "fake message"})

    actual_history = service.get_history("c1")

    assert len(actual_history) == 2
