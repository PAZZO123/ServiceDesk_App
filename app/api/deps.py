import ipaddress
import uuid
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountDisabled,
    AccountNotVerified,
    AuthenticationError,
    InvalidToken,
    PermissionDenied,
)
from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.user_service import UserService

# Database
DbSession = Annotated[AsyncSession, Depends(get_db)]


# Services
async def get_user_service(db: DbSession) -> UserService:
    return UserService(db)


async def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


UserSvc = Annotated[UserService, Depends(get_user_service)]
AuthSvc = Annotated[AuthService, Depends(get_auth_service)]

# Authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="sign with email an password",
    auto_error=False,
)

bearer_scheme=HTTPBearer(
    scheme_name="Paste an existing token",
    description=(
        "Paste and access token directly . Useful for testind expired"
        "tokens , another user's token, or a refresh tokenen (whiCh must be rejected)."
    ),
    auto_error=False,
)

async def get_token(
    form_token:Annotated[str| None, Depends(oauth2_scheme)],
    pasted:Annotated[HTTPAuthorizationCredentials |None, Depends(bearer_scheme)]
)->str:
    token=form_token or (pasted.credentials if pasted else None)
    if not token:
        raise AuthenticationError("Authorization header missing.")
    return token

async def get_current_user(
    token: Annotated[str, Depends(get_token)], users: UserSvc
) -> User:
    try:
        payload = decode_token(token, TokenType.ACCESS)
    except jwt.PyJWTError as exc:
        raise InvalidToken() from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidToken() from exc

    user = await users.get_by_id(user_id, with_profile=True)

    if user is None:
        raise InvalidToken()

    if not user.is_active:
        raise AccountDisabled()
    if user.sessions_valid_from is not None:
        issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
    if issued_at < user.sessions_valid_from:
        raise InvalidToken("This session has been ended.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_verified_user(user: CurrentUser) -> User:
    if not user.is_verified:
        raise AccountNotVerified()
    return user


VerifiedUser = Annotated[User, Depends(get_verified_user)]


# Authorization
def require_roles(*allowed: UserRole):
    async def dependency(user: VerifiedUser) -> User:
        if user.role not in allowed:
            raise PermissionDenied(
                f"This action requires one of:{','.join(r.value for r in allowed)}."
            )
        return user

    return dependency


RequireAgent = Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.ADMIN))]
RequireAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return None
    return value


async def get_client_info(request: Request) -> dict[str, str | None]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None

    return {
        "user_agent": request.headers.get("user-agent"),
        "ip_address": _valid_ip(ip),
    }


ClientInfo = Annotated[dict[str, str | None], Depends(get_client_info)]
