import uuid
from typing import Protocol

from app.domain import Chunk, Message, Organisation, Role, Scope, User, Vector


class EmailAlreadyExistsError(Exception):
    """Raised when a user with that email already exists.

    Vendor-neutral on purpose: a caller must never have to catch
    sqlalchemy.exc.IntegrityError, or the storage engine has leaked upward.
    """


class ConversationNotFoundError(Exception):
    """Raised when a conversation does not exist, or is not the caller's.

    Deliberately one error for both: telling a caller that a conversation
    exists but belongs to someone else lets them enumerate real ids.
    """


class ConversationRepository(Protocol):
    def get_history(
        self,
        conversation_id: str,
        scope: Scope,
        limit: int | None = None,
    ) -> list[Message]: ...

    def add_message(
        self, conversation_id: str, scope: Scope, message: Message
    ) -> None: ...


class UserRepository(Protocol):
    def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...
    def create(self, email: str, password_hash: str) -> User: ...


class ChunkRepository(Protocol):
    """Documents are shared across the organisation.

    This is the one place where scope means the organisation and not the user:
    a shared knowledge base is most of what an organisation is for. Uploads
    still record who contributed them.
    """

    def add(
        self,
        scope: Scope,
        document_name: str,
        chunks: list[str],
        vectors: list[Vector],
        model_id: str,
    ) -> None: ...

    def search(self, scope: Scope, vector: Vector, limit: int) -> list[Chunk]: ...

    def delete_document(self, scope: Scope, document_name: str) -> None: ...

    def list_documents(self, scope: Scope) -> list[str]: ...


class NotAMemberError(Exception):
    """Raised when a user belongs to no organisation.

    Should be impossible after signup, which creates one. If it happens the
    request must fail rather than fall back to some default tenant -- a
    default tenant is a boundary with a hole in it.
    """


class OrganisationRepository(Protocol):
    def create_with_owner(self, name: str, user_id: uuid.UUID) -> Organisation: ...

    def membership_for(
        self, user_id: uuid.UUID
    ) -> tuple[Organisation, Role] | None: ...

    def members(self, organisation_id: uuid.UUID) -> list[tuple[User, Role]]: ...

    def add_member(
        self, organisation_id: uuid.UUID, user_id: uuid.UUID, role: Role
    ) -> None: ...

    def remove_member(self, organisation_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    def is_unused_personal_workspace(self, organisation_id: uuid.UUID) -> bool:
        """One member and no data of any kind.

        Signup gives everyone a personal workspace, which otherwise makes
        invitations impossible: one-org-per-user and auto-create are mutually
        exclusive. Someone who has not started using theirs can hand it back.
        """
        ...

    def discard(self, organisation_id: uuid.UUID) -> None: ...
