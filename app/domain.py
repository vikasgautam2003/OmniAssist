"""Core application types, shared across layers.

This module must not import from any other application module.
"""

import enum
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


@dataclass(frozen=True)
class Artifact:
    """A file a tool produced, owned by the user who asked for it.

    Tools return a string, so a generated file cannot be the return value.
    It is stored here and the tool returns a short reference the UI resolves
    into a download -- keeping megabytes of base64 out of the conversation
    and out of the model's context window.
    """

    id: uuid.UUID
    filename: str
    media_type: str
    content: bytes


class Role(enum.StrEnum):
    """What a member may do.

    Three roles rather than a permission matrix: a grants system is more code
    and more ways to be subtly wrong, in exchange for flexibility nothing has
    asked for. Three roles and an explicit check can be verified by reading it.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

    def can_manage_members(self) -> bool:
        return self in (Role.OWNER, Role.ADMIN)

    def can_delete_organisation(self) -> bool:
        return self is Role.OWNER


@dataclass(frozen=True)
class Organisation:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class Scope:
    """The tenancy boundary a query runs inside.

    One object rather than two more parameters on every repository method:
    signatures stay stable as more context arrives, and "which tenant" is
    impossible to omit by accident, which matters more here than elsewhere
    because omitting it is a data breach rather than a bug.

    Carries no role: authorisation is about the action and belongs in the
    route. This is only about which rows exist.
    """

    organisation_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class Principal:
    """Who is acting, where, and with what authority.

    Resolved once per request from the token. The organisation is derived from
    the membership, never read from a request parameter -- a parameter can be
    forged, and tenancy is the one boundary that must not be.
    """

    user: User
    organisation: Organisation
    role: Role

    def scope(self) -> Scope:
        return Scope(organisation_id=self.organisation.id, user_id=self.user.id)
