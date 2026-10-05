import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.concurrency import run_in_threadpool

from app.core.config import settings


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


# Password Hashing
BCRYPT_ROUNDS = 12

def _hash_sync(password: str) -> str:

    password_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def _verify_sync(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8")[:72],
            hashed.encode("utf-8"),
        )
    except ValueError:
        return False


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hash_sync, password)


async def verify_password(plain: str, hashed: str) -> bool:
    return await run_in_threadpool(_verify_sync, plain, hashed)


# JWT _ACESS AND REFRESH TokenError


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expires_at,
        "iat": now.timestamp(),
        "jti": jti,
        "token_type": token_type.value,
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at

def create_access_token(user_id: uuid.UUID | str) -> str:
    token, _, _ = _create_token(
        subject=str(user_id),
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return token

def create_refresh_token(
    user_id: uuid.UUID | str, family_id: uuid.UUID
) -> tuple[str, str, datetime]:
    return _create_token(
        subject=str(user_id),
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={
            "require": ["exp", "iat", "sub", "jti", "token_type"],
            "verify_exp": True,
            "verify_signature": True,
        },
    )
    if payload.get("token_type") != expected_type.value:
        raise jwt.InvalidTokenError(
            f"Expected a {expected_type.value} token,got {payload.get('token_type')}"
        )
    return payload


# Email link Token

_verify_serializer = URLSafeTimedSerializer(
    settings.SECRET_KEY, salt="email-verification"
)
_reset_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="password-reset")


def create_email_verification_token(email: str) -> str:
    return _verify_serializer.dumps(email)


def verify_email_verification_token(token: str) -> str | None:
    try:
        return _verify_serializer.loads(
            token,
            max_age=settings.EMAIL_TOKEN_EXPIRE_HOURS * 3600,
        )

    except (BadSignature, SignatureExpired):
        return None


# A reset link must work ONCE. The token carries a fingerprint of the
# password hash it was made for; setting a new password makes a new hash
# (bcrypt adds a fresh salt), so every older link stops matching.
def password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode("utf-8")).hexdigest()[:16]


def create_password_reset_token(email: str, hashed_password: str) -> str:
    return _reset_serializer.dumps(
        {"email": email, "pw": password_fingerprint(hashed_password)}
    )


def verify_password_reset_token(token: str) -> tuple[str, str] | None:
    # Returns (email, fingerprint). The caller compares the fingerprint
    # with the user's CURRENT hash - only the database knows that.
    try:
        data = _reset_serializer.loads(
            token, max_age=settings.RESET_TOKEN_EXPIRE_MINUTES * 60
        )
    except (BadSignature, SignatureExpired):
        return None
    # Links made before this change hold a plain email string: refuse them.
    if not isinstance(data, dict):
        return None
    email, fingerprint = data.get("email"), data.get("pw")
    if not isinstance(email, str) or not isinstance(fingerprint, str):
        return None
    return email, fingerprint
