import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequest,
    PermissionDenied,
    RoleAlreadyExists,
    RoleInUse,
    RoleNotFound,
    UserNotFound,
)
from app.models.audit import RefreshToken
from app.models.enums import Permission
from app.models.role import PermissionRecord, Role
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.role import RoleCreate, RolePermissionsUpdate
from app.services.audit import add_audit

# Settings, not powers: holding them lets you do nothing extra, so anyone
# with role.manage may grant them (admins do not start tickets High, but
# must be able to build an agent-like role).
NOT_A_POWER = frozenset({Permission.TICKET_STARTS_HIGH.value})


class RoleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_roles(self) -> list[Role]:
        rows = await self.db.scalars(select(Role).order_by(Role.name))
        return list(rows)

    async def list_permissions(self) -> list[PermissionRecord]:
        rows = await self.db.scalars(select(PermissionRecord).order_by(PermissionRecord.code))
        return list(rows)

    async def require_role(self, role_id: uuid.UUID) -> Role:
        role = await self.db.get(Role, role_id)
        if role is None:
            raise RoleNotFound()
        return role

    async def list_users(self, pagination: PaginationParams) -> tuple[list[User], int]:
        total = await self.db.scalar(select(func.count(User.id))) or 0
        rows = await self.db.scalars(
            select(User)
            .order_by(User.full_name, User.id)
            .offset(pagination.offset)
            .limit(pagination.size)
        )
        return list(rows), total

    # ---- role management ------------------------------------------------

    async def _records(self, permissions: list[Permission]) -> list[PermissionRecord]:
        wanted = {p.value for p in permissions}
        rows = list(
            await self.db.scalars(
                select(PermissionRecord).where(PermissionRecord.code.in_(wanted))
            )
        )
        # The enum knows a code the table does not: a migration is missing.
        missing = wanted - {r.code for r in rows}
        if missing:
            raise BadRequest(f"Unknown permission(s): {', '.join(sorted(missing))}.")
        return rows

    @staticmethod
    def _check_actor_may_change(actor: User, changed: set[str]) -> None:
        # Nobody grants or removes a permission they do not hold themselves,
        # otherwise role.manage alone would be a ladder to every other power.
        beyond = changed - set(actor.role.permissions) - NOT_A_POWER
        if beyond:
            raise PermissionDenied(
                "You can only grant or remove permissions you have yourself: "
                + ", ".join(sorted(beyond))
                + "."
            )

    async def create_role(
        self, data: RoleCreate, actor: User, *, ip_address: str | None = None
    ) -> Role:
        if await self.db.scalar(select(Role.id).where(Role.name == data.name)):
            raise RoleAlreadyExists()

        records = await self._records(data.permissions)
        self._check_actor_may_change(actor, {r.code for r in records})

        role = Role(
            name=data.name,
            description=data.description,
            is_system=False,
            permission_records=records,
        )
        self.db.add(role)
        await self.db.flush()

        add_audit(
            self.db,
            actor_id=actor.id,
            entity_type="role",
            entity_id=role.id,
            action="role_created",
            changes={"name": role.name, "permissions": role.permissions},
            ip_address=ip_address,
        )
        await self.db.commit()
        return role

    async def set_permissions(
        self,
        role_id: uuid.UUID,
        data: RolePermissionsUpdate,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> Role:
        role = await self.require_role(role_id)

        # Same rule as assign_role: no self-promotion, no locking yourself out.
        if role.id == actor.role_id:
            raise PermissionDenied(
                "You cannot change the permissions of your own role. "
                "Ask someone with another role."
            )

        records = await self._records(data.permissions)
        before = set(role.permissions)
        after = {r.code for r in records}
        if before == after:
            return role
        self._check_actor_may_change(actor, before ^ after)

        # No "last holder" check is needed: to remove a permission you must
        # hold it, and your own role cannot be edited - so you keep it.
        role.permission_records = records

        add_audit(
            self.db,
            actor_id=actor.id,
            entity_type="role",
            entity_id=role.id,
            action="role_permissions_changed",
            changes={
                "added": sorted(after - before),
                "removed": sorted(before - after),
            },
            ip_address=ip_address,
        )
        await self.db.commit()
        return role

    async def delete_role(
        self, role_id: uuid.UUID, actor: User, *, ip_address: str | None = None
    ) -> None:
        role = await self.require_role(role_id)
        if role.is_system:
            raise RoleInUse("Built-in roles cannot be removed.")

        users = await self.db.scalar(select(func.count(User.id)).where(User.role_id == role.id))
        if users:
            raise RoleInUse(
                f"{users} user(s) still have this role. Give them another role first."
            )

        add_audit(
            self.db,
            actor_id=actor.id,
            entity_type="role",
            entity_id=role.id,
            action="role_deleted",
            changes={"name": role.name, "permissions": role.permissions},
            ip_address=ip_address,
        )
        await self.db.delete(role)
        await self.db.commit()

    # ---- assigning roles to users ----------------------------------------

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

        # The ladder rule again. Without it, user.manage alone could hand out
        # "admin" (to a second account you own) or demote an admin who has
        # powers you lack. The new role gives its permissions; the old role
        # takes its permissions away: you must hold both sets yourself.
        self._check_actor_may_change(actor, set(role.permissions) | set(user.role.permissions))

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

    # ---- disabling accounts ----------------------------------------------

    async def set_active(
        self,
        user_id: uuid.UUID,
        is_active: bool,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> User:
        # Disabling yourself would lock you out with nobody to undo it.
        if user_id == actor.id:
            raise PermissionDenied("You cannot disable or enable your own account.")

        user = await self.db.get(User, user_id)
        if user is None:
            raise UserNotFound()

        # Same ladder rule as assign_role: switching off an account takes
        # away every power its role has, so you must hold them all yourself.
        # A user manager cannot disable an admin who has more powers.
        self._check_actor_may_change(actor, set(user.role.permissions))

        if user.is_active == is_active:
            return user

        user.is_active = is_active
        if not is_active:
            # Sign the user out everywhere, in the SAME transaction.
            # Access tokens: refused because of sessions_valid_from (and
            # is_active). Refresh tokens: revoked, so they do not come back
            # to life if the account is enabled again later.
            now = datetime.now(UTC)
            user.sessions_valid_from = now
            await self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )

        add_audit(
            self.db,
            actor_id=actor.id,
            entity_type="user",
            entity_id=user.id,
            action="account_enabled" if is_active else "account_disabled",
            changes={"is_active": {"from": not is_active, "to": is_active}},
            ip_address=ip_address,
        )
        await self.db.commit()
        return user
