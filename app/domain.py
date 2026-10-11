"""Core application types, shared across layers.

This module must not import from any other application module.
"""

import uuid
from dataclasses import dataclass

Message = dict[str, str]
Vector = list[float]


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
