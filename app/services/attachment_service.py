import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core import storage
from app.core.config import settings
from app.core.exceptions import AttachmentNotFound, BadRequest
from app.core.permissions import TicketPermissions
from app.models.attachment import Attachment
from app.models.ticket import Comment, Ticket
from app.models.user import User
from app.services.audit import add_audit

logger = logging.getLogger(__name__)


class AttachmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # Reads
    async def require_by_id(self, attachment_id: uuid.UUID) -> Attachment:
        result = await self.db.execute(
            select(Attachment)
            .where(Attachment.id == attachment_id)
            .options(joinedload(Attachment.uploader))
        )
        attachment = result.unique().scalar_one_or_none()
        if attachment is None:
            raise AttachmentNotFound()
        return attachment

    async def list_for_ticket(
        self, ticket: Ticket, perms: TicketPermissions
    ) -> list[Attachment]:
        visible_comment_ids = select(Comment.id).where(
            Comment.ticket_id == ticket.id,
            *perms.comment_conditions(),
        )

        stmt = (
            select(Attachment)
            .where(
                or_(
                    Attachment.ticket_id == ticket.id,
                    Attachment.comment_id.in_(visible_comment_ids),
                )
            )
            .options(joinedload(Attachment.uploader))
            .order_by(Attachment.created_at)
        )

        rows = await self.db.execute(stmt)
        return list(rows.unique().scalars().all())

    # Writes
    
    async def upload(
        self,
        upload_file,
        uploader: User,
        *,
        ticket: Ticket | None = None,
        comment: Comment | None = None,
        ip_address: str | None = None,
    ) -> Attachment:
       
        if (ticket is None) == (comment is None):
            raise BadRequest(
                "An attachment must belong to exactly one ticket or one comment."
            )

        relative_path, detected_type, size = await storage.save_upload(
            upload_file, settings.max_upload_bytes
        )
        if upload_file.content_type and upload_file.content_type != detected_type:
            logger.warning(
                "upload_type_mismatch claimed=%s detected=%s user=%s",
                upload_file.content_type,
                detected_type,
                uploader.id,
            )

        try:
            attachment = Attachment(
                ticket_id=ticket.id if ticket else None,
                comment_id=comment.id if comment else None,
                original_filename=storage.safe_header_filename(
                    upload_file.filename or "upload"
                ),
                storage_path=relative_path,
                content_type=detected_type,
                size_bytes=size,
                uploaded_by=uploader.id,
            )
            self.db.add(attachment)
            await self.db.flush()

            add_audit(
                self.db,
                actor_id=uploader.id,
                entity_type="ticket",
                entity_id=ticket.id if ticket else comment.ticket_id, 
                action="attachment_added",
                changes={
                    "attachment_id": str(attachment.id),
                    "filename": attachment.original_filename,
                    "content_type": detected_type,
                    "size_bytes": size,
                },
                ip_address=ip_address,
            )

            await self.db.commit()

        except Exception:
            storage.delete_file(relative_path)
            raise

        return await self.require_by_id(attachment.id)

    async def delete(
        self,
        attachment: Attachment,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> None:
        path = attachment.storage_path

        add_audit(
            self.db,
            actor_id=actor.id,
            entity_type="ticket",
            entity_id=attachment.ticket_id or attachment.comment_id,  # type: ignore[arg-type]
            action="attachment_removed",
            changes={
                "attachment_id": str(attachment.id),
                "filename": attachment.original_filename,
            },
            ip_address=ip_address,
        )

        await self.db.delete(attachment)
        await self.db.commit()

        # Only now, once the row is definitely gone.
        storage.delete_file(path)