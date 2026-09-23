import uuid
from datetime import UTC, datetime, timezone

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (AccountDisabled, AccountNotVerified,
                                 InvalidCredentials, InvalidToken,
                                 TokenReuseDetected)
from app.core.security import (TokenType, create_access_token,
                               create_refresh_token, decode_token,
                               hash_password, verify_password)
from app.models.audit import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair
from app.services.user_service import UserService


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserService(db)
        # Composing services rather than duplicating queries. Both share
        # the SAME session, so anything they do together is one
        # transaction.

    # ==================================================================
    #  LOGIN
    # ==================================================================
    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)

        if user is None:
            await hash_password(password)
            raise InvalidCredentials()

        if not await verify_password(password, user.hashed_password):
            raise InvalidCredentials()

        if not user.is_active:
            raise AccountDisabled()

        if not user.is_verified:
            raise AccountNotVerified()

        return user

    async def issue_token_pair(
        self,
        user: User,
        *,
        family_id: uuid.UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        if family_id is None:
            family_id = uuid.uuid4()

        access = create_access_token(user_id=user.id, role=user.role.value)

        refresh, jti, expires_at = create_refresh_token(
            user_id=user.id, family_id=family_id
        )

        self.db.add(
            RefreshToken(
                user_id=user.id,
                jti=jti,
                family_id=family_id,
                expires_at=expires_at,
                user_agent=(user_agent or "")[:255] or None,
                ip_address=ip_address,
            )
        )
        await self.db.commit()

        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.ACCES_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def rotate_refresh_token(
        self,
        raw_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        try:
            payload = decode_token(raw_token, TokenType.REFRESH)
        except jwt.PyJWTError as exc:
            raise InvalidToken() from exc

        jti: str = payload["jti"]
        user_id = uuid.UUID(payload["sub"])

        stored = await self.db.scalar(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )

        if stored is None:
            raise InvalidToken()

        if stored.revoked_at is not None:
            await self._revoke_family(stored.family_id)
            raise TokenReuseDetected()

        now = datetime.now(UTC)
        if stored.expires_at <= now:
            raise InvalidToken()
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            await self._revoke_family(stored.family_id)
            raise InvalidToken()

        stored.revoked_at = now

        return await self.issue_token_pair(
            user,
            family_id=stored.family_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def _revoke_family(self, family_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self.db.commit()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Log a user out of every device, immediately."""
        now = datetime.now(timezone.utc)

        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(sessions_valid_from=now)
        )

        await self.db.commit()

    async def logout(self, raw_token: str) -> None:
       
        try:
            payload = decode_token(raw_token, TokenType.REFRESH)
        except jwt.PyJWTError:
            return
        await self.revoke_all_for_user(uuid.UUID(payload["sub"]))
