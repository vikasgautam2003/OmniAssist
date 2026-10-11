"""Core application types, shared across layers.

This module must not import from any other application module.
"""

import uuid
from dataclasses import dataclass

Vector = list[float]


@dataclass(frozen=True)
class ToolCall:
    """One request from the model to run a tool.

    `arguments` stays the provider's raw JSON string rather than a parsed dict:
    every provider emits it that way, and round-tripping through a dict would
    re-serialise it differently from what the model actually sent.
    """

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Message:
    """One turn in a conversation.

    A tool call is a turn, not a separate store: keeping tool state beside the
    conversation would give two sources of truth about what was said.
    """

    role: str
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    email: str
    password_hash: str


@dataclass(frozen=True)
class Chunk:
    """A retrievable passage of a document, with enough identity to cite it."""

    content: str
    document_name: str
    chunk_index: int
