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
from app.core.permissions import TicketPermissions, load_team_ids
from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.enums import Permission
from app.models.user import User
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.comment_service import CommentService
from app.services.notification_service import NotificationService
from app.services.role_service import RoleService
from app.services.team_service import TeamService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

# Database
DbSession = Annotated[AsyncSession, Depends(get_db)]


# Services
async def get_user_service(db: DbSession) -> UserService:
    return UserService(db)


async def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


async def get_ticket_service(db: DbSession) -> TicketService:
    return TicketService(db)


async def get_comment_service(db: DbSession) -> CommentService:
    return CommentService(db)


async def get_attachment_service(db: DbSession) -> AttachmentService:
    return AttachmentService(db)


async def get_team_service(db: DbSession) -> TeamService:
    return TeamService(db)


async def get_role_service(db: DbSession) -> RoleService:
    return RoleService(db)


async def get_notification_service(db: DbSession) -> NotificationService:
    return NotificationService(db)


UserSvc = Annotated[UserService, Depends(get_user_service)]
AuthSvc = Annotated[AuthService, Depends(get_auth_service)]
TicketSvc = Annotated[TicketService, Depends(get_ticket_service)]
CommentSvc = Annotated[CommentService, Depends(get_comment_service)]
AttachmentSvc = Annotated[AttachmentService, Depends(get_attachment_service)]
TeamSvc = Annotated[TeamService, Depends(get_team_service)]
RoleSvc = Annotated[RoleService, Depends(get_role_service)]
NotificationSvc = Annotated[NotificationService, Depends(get_notification_service)]

# Authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="sign with email and password",
    auto_error=False,
)

bearer_scheme=HTTPBearer(
    scheme_name="Paste an existing token",
    description=(
        "Paste and access token directly. Useful for testind expired"
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

    user = await users.get_by_id(user_id)

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
# Several permissions = ANY of them is enough.
def require_permission(*permissions: Permission):
    async def dependency(user: VerifiedUser) -> User:
        if not any(user.role.grants(p) for p in permissions):
            names = "' or '".join(p.value for p in permissions)
            raise PermissionDenied(f"This action requires the '{names}' permission.")
        return user

    return dependency


RequireTeamManager = Annotated[User, Depends(require_permission(Permission.TEAM_MANAGE))]
RequireUserManager = Annotated[User, Depends(require_permission(Permission.USER_MANAGE))]
RequireRoleManager = Annotated[User, Depends(require_permission(Permission.ROLE_MANAGE))]
# Reading the role list: needed both to assign roles and to edit them.
RequireRoleReader = Annotated[
    User, Depends(require_permission(Permission.USER_MANAGE, Permission.ROLE_MANAGE))
]

async def get_permissions(user: VerifiedUser, db: DbSession) -> TicketPermissions:
    return TicketPermissions(user=user, team_ids=await load_team_ids(db, user))

Perms = Annotated[TicketPermissions, Depends(get_permissions)]


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return None
    return value


async def get_client_info(request: Request) -> dict[str, str | None]:
    # NOT the X-Forwarded-For header: any client can send it with any value,
    # so the audit log would record a fake IP. Behind a real proxy, start
    # uvicorn with --proxy-headers --forwarded-allow-ips=<proxy ip>: uvicorn
    # then trusts the header ONLY from that proxy and puts the real address
    # here - for the audit log and the rate limiter alike.
    ip = request.client.host if request.client else None

    return {
        "user_agent": request.headers.get("user-agent"),
        "ip_address": _valid_ip(ip),
    }


ClientInfo = Annotated[dict[str, str | None], Depends(get_client_info)]
