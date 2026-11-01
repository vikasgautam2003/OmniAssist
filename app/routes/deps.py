import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain import Principal, User
from app.repositories.base import OrganisationRepository, UserRepository
from app.repositories.organisations import PostgresOrganisationRepository
from app.repositories.postgres import PostgresUserRepository
from app.security.tokens import decode_access_token

# auto_error=False so a missing header reaches our handler rather than
# producing FastAPI's own 403, which would be the wrong status code.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = "Not authenticated"


def get_user_repository() -> UserRepository:
    return PostgresUserRepository()


def get_organisation_repository() -> OrganisationRepository:
    return PostgresOrganisationRepository()


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


def get_principal(user: "CurrentUser") -> Principal:
    """Resolve the caller to a user, an organisation and a role.

    The organisation comes from the membership, never from a request
    parameter. A parameter can be forged, and tenancy is the one boundary
    that must not be.
    """
    membership = get_organisation_repository().membership_for(user.id)

    if membership is None:
        # Signup always creates one, so this means the data is inconsistent.
        # Failing is correct: a default tenant is a boundary with a hole in it.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not belong to an organisation."
        )

    organisation, role = membership
    return Principal(user=user, organisation=organisation, role=role)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_member_management(principal: "CurrentPrincipal") -> Principal:
    """Authorisation, deliberately at the route rather than the repository.

    Isolation -- can this organisation see this row -- stays in the query,
    because forgetting it is a data breach. Authorisation is about the
    *action*, and the route is where the action is named.
    """
    if not principal.role.can_manage_members():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"A {principal.role.value} cannot manage members.",
        )

    return principal


CanManageMembers = Annotated[Principal, Depends(require_member_management)]
