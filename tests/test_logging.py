import json
import uuid
from io import StringIO
from typing import Any

import pytest
import structlog

from app.domain import ToolCall
from app.observability.logging import bind, configure, get_logger, new_request
from app.tools.base import ToolContext
from app.tools.calculator import Calculator
from app.tools.registry import ToolRegistry


@pytest.fixture
def captured() -> Any:
    """Capture structlog output as parsed JSON records."""
    stream = StringIO()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines() if line]
    configure(json_output=False)


def test_every_line_in_a_request_shares_one_id(captured: Any) -> None:
    """Without correlation, a hundred interleaved requests produce a hundred
    unrelated lines and no way to reassemble any single one."""
    log = get_logger("test")
    request_id = new_request(uuid.uuid4())
    log.info("first")
    log.info("second")

    records = captured()
    assert {r["request_id"] for r in records} == {request_id}
    assert all("user_id" in r for r in records)


def test_a_new_request_does_not_inherit_the_last_one(captured: Any) -> None:
    """Context variables persist until cleared; a leaked user_id would
    attribute one person's activity to another."""
    log = get_logger("test")
    new_request(uuid.uuid4())
    log.info("first")

    second_id = new_request()
    log.info("second")

    records = captured()
    assert records[1]["request_id"] == second_id
    assert "user_id" not in records[1]


def test_a_tool_call_is_logged_with_its_outcome(captured: Any) -> None:
    registry = ToolRegistry([Calculator()])
    context = ToolContext(user_id=uuid.uuid4())

    registry.run(
        ToolCall(id="c1", name="calculate", arguments='{"expression":"2+2"}'), context
    )

    record = next(r for r in captured() if r["event"] == "tool.call")
    assert record["tool"] == "calculate"
    assert record["outcome"] == "ok"
    assert record["duration_ms"] >= 0


def test_a_failing_tool_is_logged_as_failed(captured: Any) -> None:
    registry = ToolRegistry([Calculator()])
    context = ToolContext(user_id=uuid.uuid4())

    registry.run(
        ToolCall(id="c1", name="calculate", arguments='{"expression":"1/0"}'), context
    )

    record = next(r for r in captured() if r["event"] == "tool.call")
    assert record["outcome"] == "failed"


def test_tool_arguments_are_never_logged(captured: Any) -> None:
    """A model composes tool arguments from document text, which may be the
    user's private data. Logs outlive the request and are read by more people."""
    registry = ToolRegistry([Calculator()])
    context = ToolContext(user_id=uuid.uuid4())
    secret = "48271 * 9183"

    registry.run(
        ToolCall(id="c1", name="calculate", arguments=f'{{"expression":"{secret}"}}'),
        context,
    )

    assert secret not in json.dumps(captured())


def test_bound_values_reach_later_lines(captured: Any) -> None:
    log = get_logger("test")
    new_request()
    bind(conversation_id="c-42")
    log.info("something")

    assert captured()[0]["conversation_id"] == "c-42"
