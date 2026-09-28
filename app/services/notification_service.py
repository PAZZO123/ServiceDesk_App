import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotificationNotFound
from app.models.audit import Notification
from app.models.user import User
from app.schemas.common import PaginationParams


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(
        self, user: User, pagination: PaginationParams, *, unread_only: bool = False
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user.id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))

        total = await self.db.scalar(select(func.count(Notification.id)).where(*conditions)) or 0
        rows = await self.db.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(pagination.offset)
            .limit(pagination.size)
        )
        return list(rows), total
    async def unread_count(self, user_id: uuid.UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )

    async def mark_read(self, user: User, notification_id: uuid.UUID) -> Notification:
        notification = await self.db.get(Notification, notification_id)
        # Someone else's notification is "not found", never "forbidden".
        if notification is None or notification.user_id != user.id:
            raise NotificationNotFound()
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            await self.db.commit()
        return notification

    async def mark_all_read(self, user: User) -> None:
        # One UPDATE statement, not a loop that loads every row into Python.
        await self.db.execute(
            update(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        await self.db.commit()