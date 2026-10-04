import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Notification
from app.models.enums import NotificationType, Permission
from app.models.role import PermissionRecord, role_permissions
from app.models.user import User


def _roles_granting(permission: Permission) -> Select:
    return (
        select(role_permissions.c.role_id)
        .join(PermissionRecord, PermissionRecord.id == role_permissions.c.permission_id)
        .where(PermissionRecord.code == permission.value)
    )


async def oversight_user_ids(db: AsyncSession, *, internal: bool = False) -> set[uuid.UUID]:
    stmt = select(User.id).where(
        User.is_active.is_(True),
        User.notify_in_app.is_(True),
        User.role_id.in_(_roles_granting(Permission.TICKET_VIEW_ALL)),
    )
    if internal:
    
        stmt = stmt.where(User.role_id.in_(_roles_granting(Permission.COMMENT_READ_INTERNAL)))
    return set((await db.scalars(stmt)).all())


async def notify_oversight(
    db: AsyncSession,
    kind: NotificationType,
    payload: dict[str, Any],
    *,
    exclude: set[uuid.UUID],
    internal: bool = False,
) -> None:
  
    for user_id in await oversight_user_ids(db, internal=internal) - exclude:
        db.add(Notification(user_id=user_id, type=kind, payload=payload))