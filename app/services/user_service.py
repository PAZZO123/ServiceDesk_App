import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import UserAlreadyExists, UserNotFound
from app.core.security import hash_password
from app.models.user import User, UserProfile
from app.schemas.user import UserCreate, UserProfileUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self, user_id: uuid.UUID, *, with_profile: bool = False
    ) -> User | None:
        stmt = select(User).where(User.id == user_id)
        if with_profile:
            stmt = stmt.options(selectinload(User.profile))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(
        self, email: str, *, with_profile: bool = False
    ) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        if with_profile:
            stmt = stmt.options(selectinload(User.profile))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def require_by_email(self, email: str) -> User:

        user = await self.get_by_email(email)
        if user is None:
            raise UserNotFound()
        return user

    async def require_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.get_by_id(user_id, with_profile=True)
        if user is None:
            raise UserNotFound()
        return user

    # Creates
    async def create(self, data: UserCreate) -> User:
        user = User(
            email=data.email,
            full_name=data.full_name,
            hashed_password=await hash_password(data.password),
        )
        self.db.add(user)

        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            if "uq_users_email" in str(exc.orig) or "ix_users_email" in str(exc.orig):
                raise UserAlreadyExists() from exc
            raise
        profile = UserProfile(user_id=user.id)
        self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(
            user, attribute_names=["created_at", "updated_at", "role"]
        )
        return user

    async def set_verified(self, user: User) -> User:
        user.is_verified = True
        await self.db.commit()
        return user

    async def set_password(self, user: User, new_password: str) -> User:
        user.hashed_password = await hash_password(new_password)
        await self.db.commit()
        return user

    async def update_profile(self, user: User, data: UserProfileUpdate) -> UserProfile:
        profile = user.profile
        if profile is None:
            profile = UserProfile(user_id=user.id)
            self.db.add(profile)

        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(profile, field, value)
        await self.db.commit()
        return profile
