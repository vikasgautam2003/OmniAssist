import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain import User
from app.repositories.base import UserRepository
from app.repositories.postgres import PostgresUserRepository
from app.security.tokens import decode_access_token

# auto_error=False so a missing header reaches our handler rather than
# producing FastAPI's own 403, which would be the wrong status code.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = "Not authenticated"


def get_user_repository() -> UserRepository:
    return PostgresUserRepository()


def _unauthenticated() -> HTTPException:
    # RFC 9110: a 401 must say how to authenticate.
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        _UNAUTHENTICATED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve `Authorization: Bearer <token>` to a user, or raise 401.

    The user is looked up rather than trusted from the token alone: a JWT
    cannot be revoked before it expires, so a deleted account would otherwise
    keep access for the remainder of its token's lifetime. The cost is one
    query per request — the thing v0.3's cache is for.
    """
    if credentials is None:
        raise _unauthenticated()

    try:
        subject = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        # Covers expired, tampered, wrong-algorithm and malformed tokens alike.
        # The client learns only that it is not authenticated; which of those
        # went wrong is not its business.
        raise _unauthenticated() from exc

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise _unauthenticated() from exc

    user = get_user_repository().get_by_id(user_id)

    if user is None:
        raise _unauthenticated()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
