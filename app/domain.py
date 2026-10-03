"""Core application types, shared across layers.

This module must not import from any other application module.
"""

import uuid
from dataclasses import dataclass

Message = dict[str, str]


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    email: str
    password_hash: str
