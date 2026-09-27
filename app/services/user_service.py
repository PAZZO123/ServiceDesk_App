import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExists, UserNotFound
from app.core.security import hash_password
from app.models.enums import SystemRole
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserProfileUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.scalar(select(User).where(User.id == user_id))

    async def get_by_email(self, email: str) -> User | None:
        # lower(email) so the query can use the uq_users_email_lower index
        return await self.db.scalar(
            select(User).where(func.lower(User.email) == email.lower())
        )

    async def require_by_email(self, email: str) -> User:

        user = await self.get_by_email(email)
        if user is None:
            raise UserNotFound()
        return user

    async def require_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        return user

    # Creates
    async def create(self, data: UserCreate) -> User:
        role = await self.db.scalar(select(Role).where(Role.name == SystemRole.REQUESTER))
        if role is None:
            raise RuntimeError("The 'requester' role is missing. Run: alembic upgrade head")

        user = User(
            email=data.email,
            full_name=data.full_name,
            hashed_password=await hash_password(data.password),
            role=role,
        )
        self.db.add(user)

        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            if "uq_users_email_lower" in str(exc.orig):
                raise UserAlreadyExists() from exc
            raise

        await self.db.commit()
        await self.db.refresh(user, attribute_names=["created_at", "updated_at"])
        return user

    async def set_verified(self, user: User) -> User:
        user.is_verified = True
        await self.db.commit()
        return user

    async def set_password(self, user: User, new_password: str) -> User:
        user.hashed_password = await hash_password(new_password)
        await self.db.commit()
        return user

    async def update_profile(self, user: User, data: UserProfileUpdate) -> User:
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(user, field, value)
        await self.db.commit()
        return user
