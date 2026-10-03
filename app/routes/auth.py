from functools import lru_cache

from fastapi import APIRouter, HTTPException, status

from app.repositories.base import EmailAlreadyExistsError, UserRepository
from app.repositories.postgres import PostgresUserRepository
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.security.password import hash_password, verify_password
from app.security.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

_CREDENTIALS_ERROR = "Incorrect email or password"


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    return PostgresUserRepository()


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A throwaway hash used to keep failed logins constant-time.

    Verifying against it costs the same as verifying a real password, so an
    unknown email takes as long as a wrong one. Computed lazily: importing a
    module should not burn CPU.
    """
    return hash_password("not-a-real-password")


@router.post(
    "/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def signup(credentials: SignupRequest) -> TokenResponse:
    repository = get_user_repository()

    try:
        user = repository.create(credentials.email, hash_password(credentials.password))
    except EmailAlreadyExistsError:
        # The unique constraint is the guarantee; this turns the collision into
        # a 409 rather than a 500. Checking first would be a check-then-act race.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with that email already exists"
        ) from None

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest) -> TokenResponse:
    repository = get_user_repository()
    user = repository.get_by_email(credentials.email)

    if user is None:
        # Burn the same work an existing user would cost. Without this the
        # response time alone reveals which emails are registered, which
        # defeats the identical error message below.
        verify_password(credentials.password, _dummy_hash())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENTIALS_ERROR)

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _CREDENTIALS_ERROR)

    return TokenResponse(access_token=create_access_token(str(user.id)))
