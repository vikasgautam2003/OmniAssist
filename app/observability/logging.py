import logging
import sys
import uuid
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

# Named "observability" rather than "logging" so `import logging` inside this
# package still reaches the standard library.


def configure(json_output: bool) -> None:
    """Set up structlog once, at startup.

    JSON in production because logs are read by a machine first -- grep is not
    a query language, and the v1.0 dashboards need fields, not prose. Pretty
    output locally because a human is reading it.
    """
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)


def new_request(user_id: uuid.UUID | None = None) -> str:
    """Begin a request scope and return its id.

    Every log line emitted afterwards carries this id without being passed it,
    because context variables follow the task. Without correlation, a hundred
    interleaved requests produce a hundred unrelated lines and no way to
    reassemble any single one of them.
    """
    clear_contextvars()
    request_id = str(uuid.uuid4())
    bind_contextvars(request_id=request_id)

    if user_id is not None:
        bind_contextvars(user_id=str(user_id))

    return request_id


def bind(**values: Any) -> None:
    bind_contextvars(**values)
