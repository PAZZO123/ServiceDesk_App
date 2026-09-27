import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, PermissionDenied, UserNotFound
from app.models.role import Role
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services.audit import add_audit


class RoleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_roles(self) -> list[Role]:
        rows = await self.db.scalars(select(Role).order_by(Role.name))
        return list(rows)

    async def list_users(self, pagination: PaginationParams) -> tuple[list[User], int]:
        total = await self.db.scalar(select(func.count(User.id))) or 0
        rows = await self.db.scalars(
            select(User)
            .order_by(User.full_name, User.id)
            .offset(pagination.offset)
            .limit(pagination.size)
        )
        return list(rows), total

    async def assign_role(
        self,
        user_id: uuid.UUID,
        role_name: str,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> User:
        # Nobody changes their own role: no self-promotion, no locking yourself out.
        if user_id == actor.id:
            raise PermissionDenied("You cannot change your own role. Ask another administrator.")

        user = await self.db.get(User, user_id)
        if user is None:
            raise UserNotFound()

        role = await self.db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            raise BadRequest(f"There is no role called {role_name!r}.")

        if user.role_id == role.id:
            return user

        previous = user.role.name
        user.role = role

        add_audit(
            self.db,
            actor_id=actor.id,
            entity_type="user",
            entity_id=user.id,
            action="role_changed",
            changes={"role": {"from": previous, "to": role.name}},
            ip_address=ip_address,
        )

        await self.db.commit()
        return user
