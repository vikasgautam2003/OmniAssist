from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

# Pinned here rather than read from the token: the algorithm must never be
# chosen by attacker-controlled input (the "alg: none" / algorithm-confusion
# vulnerability class).
ALGORITHM = "HS256"


def create_access_token(subject: str) -> str:
    """Mint a signed token identifying `subject` — the user's id.

    The payload is signed, not encrypted: anyone holding the token can read it.
    Nothing secret belongs in here.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    """Verify a token's signature and expiry, returning its subject.

    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure. The
    caller decides how those become HTTP responses — this module has no opinion
    about HTTP.
    """
    settings = get_settings()

    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[ALGORITHM],
    )

    return str(payload["sub"])
