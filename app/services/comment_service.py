
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core import storage
from app.core.exceptions import CommentNotFound
from app.core.permissions import TicketPermissions
from app.models.attachment import Attachment
from app.models.audit import AuditLog, Notification
from app.models.enums import NotificationType, TicketOwnerRole
from app.models.ticket import Comment, Ticket
from app.models.user import User
from app.realtime.events import emit_ticket_event
from app.schemas.comment import CommentCreate, CommentUpdate
from app.schemas.common import PaginationParams

PREVIEW_CHARS = 140


class CommentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _base_query(self):
        return select(Comment).options(joinedload(Comment.author))

    async def require_by_id(self, comment_id: uuid.UUID) -> Comment:
        result = await self.db.execute(
            self._base_query().where(Comment.id == comment_id)
        )
        comment = result.unique().scalar_one_or_none()
        if comment is None:
            raise CommentNotFound()
        return comment

    async def list_for_ticket(
        self,
        ticket: Ticket,
        perms: TicketPermissions,
        pagination: PaginationParams,
    ) -> tuple[list[Comment], int]:

        conditions = [Comment.ticket_id == ticket.id, *perms.comment_conditions()]

        total = (
            await self.db.scalar(
                select(func.count(Comment.id)).where(*conditions)
            )
            or 0
        )

        stmt = (
            self._base_query()
            .where(*conditions)
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset(pagination.offset)
            .limit(pagination.size)
        )

        rows = (await self.db.execute(stmt)).unique().scalars().all()
        return list(rows), total

    async def create(
        self,
        ticket: Ticket,
        data: CommentCreate,
        author: User,
        perms: TicketPermissions,
        *,
        ip_address: str | None = None,
        commit: bool = True,
    ) -> Comment:
        now = datetime.now(UTC)

        comment = Comment(
            ticket_id=ticket.id,
            author_id=author.id,
            body=data.body,
            is_internal=data.is_internal,
        )
        self.db.add(comment)
        await self.db.flush()

        if (
            ticket.first_response_at is None
            and not comment.is_internal
            and not ticket.has_owner(author.id, TicketOwnerRole.REQUESTER)
        ):
            ticket.first_response_at = now

        self._add_audit(
            actor_id=author.id,
            ticket_id=ticket.id,
            action="commented",
            changes={
                "comment_id": str(comment.id),
                "internal": comment.is_internal,
                "preview": data.body[:PREVIEW_CHARS],
            },
            ip_address=ip_address,
        )

        self._notify(ticket, comment, author)
        await emit_ticket_event(
            self.db, ticket.id, "comment_added", internal=comment.is_internal
        )
        if commit:
            await self.db.commit()
        return await self.require_by_id(comment.id)

    async def update(
        self,
        comment: Comment,
        data: CommentUpdate,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> Comment:
        if comment.body == data.body:
            return comment

        previous = comment.body
        comment.body = data.body

        self._add_audit(
            actor_id=actor.id,
            ticket_id=comment.ticket_id,
            action="comment_edited",
            changes={
                "comment_id": str(comment.id),
                "from": previous[:PREVIEW_CHARS],
                "to": data.body[:PREVIEW_CHARS],
            },
            ip_address=ip_address,
        )
        await emit_ticket_event(
            self.db, comment.ticket_id, "comment_edited", internal=comment.is_internal
        )

        await self.db.commit()
        return await self.require_by_id(comment.id)

    async def delete(
        self,
        comment: Comment,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> None:
        self._add_audit(
            actor_id=actor.id,
            ticket_id=comment.ticket_id,
            action="comment_deleted",
            changes={
                "comment_id": str(comment.id),
                "author_id": str(comment.author_id),
                "preview": comment.body[:PREVIEW_CHARS],
            },
            ip_address=ip_address,
        )
        paths = list(
            await self.db.scalars(
                select(Attachment.storage_path).where(
                    Attachment.comment_id == comment.id
                )
            )
        )
        await emit_ticket_event(
            self.db, comment.ticket_id, "comment_deleted", internal=comment.is_internal
        )

        await self.db.delete(comment)

        await self.db.commit()
        for path in paths:
            storage.delete_file(path)

    # Internals
    def _notify(self, ticket: Ticket, comment: Comment, author: User) -> None:
        requester_id = ticket.requester.id if ticket.requester else None
        assignee_id = ticket.assignee.id if ticket.assignee else None

        recipients: set[uuid.UUID | None]

        if comment.is_internal:
            recipients = {assignee_id}
        elif author.id == requester_id:
            recipients = {assignee_id}
        else:
            recipients = {requester_id, assignee_id}

        # Watchers hear about public comments only - a watcher may be a requester.
        if not comment.is_internal:
            recipients.update(watcher.id for watcher in ticket.watchers)

        recipients.discard(None)
        recipients.discard(author.id)

        for user_id in recipients:
            self.db.add(
                Notification(
                    user_id=user_id,
                    type=NotificationType.COMMENT_ADDED,
                    payload={
                        "ticket_id": str(ticket.id),
                        "reference": ticket.reference,
                        "comment_id": str(comment.id),
                        "author": author.full_name,
                        "internal": comment.is_internal,
                        "preview": comment.body[:PREVIEW_CHARS],
                    },
                )
            )

    def _add_audit(
        self,
        *,
        actor_id: uuid.UUID | None,
        ticket_id: uuid.UUID,
        action: str,
        changes: dict[str, Any],
        ip_address: str | None = None,
    ) -> None:
        self.db.add(
            AuditLog(
                actor_id=actor_id,
                entity_type="ticket",
                entity_id=ticket_id,
                action=action,
                changes=changes,
                ip_address=ip_address,
            )
        )
