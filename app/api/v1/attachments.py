import logging
import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import ClientInfo, DbSession, Perms
from app.core import storage
from app.core.exceptions import AttachmentNotFound, PermissionDenied
from app.models.attachment import Attachment
from app.models.ticket import Ticket
from app.schemas.attachment import AttachmentRead
from app.services.attachment_service import AttachmentService
from app.services.comment_service import CommentService
from app.services.ticket_service import TicketService

logger=logging.getLogger(__name__)
router=APIRouter(tags=["Attachements"])
def _attachments(db:DbSession)->AttachmentService:
    return AttachmentService(db)

def _tickets(db:DbSession) ->TicketService:
    return TicketService(db)

def _comments(db:DbSession)->CommentService:
    return CommentService(db)


AttachmentSvc = Annotated[AttachmentService, Depends(_attachments)]
TicketSvc = Annotated[TicketService, Depends(_tickets)]
CommentSvc = Annotated[CommentService, Depends(_comments)]


async def _ticket_for_attachment(
    attachement:Attachment,
    tickets:TicketService,
    comments:CommentService,
    perms:Perms
    
)->Ticket:
    if attachement.ticket_id is not None:
        ticket= await tickets.get_by_id(attachement.ticket_id)
    else:
        comment= await comments.require_by_id(attachement.comment_id)
        if not perms.can_see_comment(comment):
            raise AttachmentNotFound()
        ticket= await tickets.get_by_id(comment.ticket_id)
    if ticket is None or not perms.can_view(ticket):
        raise AttachmentNotFound()
    return ticket

#Uploads
@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        413: {"description": "File too large"},
        415: {"description": "File type not accepted"},
    },
)
async def upload_to_ticket(
    ticket_id:uuid.UUID,
    file: Annotated[UploadFile, File(description="the file to attach.")],
    tickets:TicketSvc,
    attachments:AttachmentSvc,
    perms:Perms,
    client:ClientInfo,
):
    ticket= await tickets.require_by_id(ticket_id)
    perms.require_comment(ticket)
    return await attachments.upload(
        file, 
        uploader=perms.user,
        ticket=ticket,
        ip_address=client["ip_address"],
        
    )

@router.post(
    "/comments/{comment_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a file to your comment",
) 
async def upload_to_comment(
    comment_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="The file to attach.")],
    attachments: AttachmentSvc,
    tickets: TicketSvc,
    comments: CommentSvc,
    perms: Perms,
    client: ClientInfo,
):
    comment = await comments.require_by_id(comment_id)
    ticket = await tickets.get_by_id(comment.ticket_id)

    if ticket is None or not perms.can_view(ticket) or not perms.can_see_comment(comment):
        raise AttachmentNotFound()

    if not perms.can_edit_comment(comment):
        raise PermissionDenied("You can only attach files to your own comments.")

    return await attachments.upload(
        file,
        uploader=perms.user,
        comment=comment,
        ip_address=client["ip_address"],
    )
    
#List
@router.get(
    "/tickets/{ticket_id}/attachments",
    response_model=list[AttachmentRead],
    summary="Every file on a ticket"
)
async def list_attachment(
    ticket_id:uuid.UUID,
    attachments:AttachmentSvc,
    tickets:TicketSvc,
    perms:Perms,
):
    ticket =  await tickets.require_by_id(ticket_id)
    perms.require_view(ticket)
    return await attachments.list_for_ticket(ticket, perms)

#Download

@router.get(
    "/attachments/{attachment_id}/download",
    summary="Download a file",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_attachment(
    attachment_id: uuid.UUID,
    attachments: AttachmentSvc,
    tickets: TicketSvc,
    comments: CommentSvc,
    perms: Perms,
) -> StreamingResponse:
    attachment = await attachments.require_by_id(attachment_id)
    await _ticket_for_attachment(attachment, tickets, comments, perms)
    path = storage.absolute_path(attachment.storage_path)
    if not path.is_file():
        logger.error(
            "attachment_file_missing id=%s path=%s",
            attachment.id,
            attachment.storage_path,
        )
        raise AttachmentNotFound("The stored file is missing.")

  
    name = attachment.original_filename
    ascii_name = name.encode("ascii", "replace").decode("ascii")

    return StreamingResponse(
        storage.stream_file(attachment.storage_path),
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; '
                f"filename*=UTF-8''{quote(name)}"
            ),
           
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(attachment.size_bytes),
            "Cache-Control": "private, no-store",
        },
    )
    
    
#Delete
@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an attachment"
)
async def delete_attachment(
    attachment_id:uuid.UUID,
    attachments:AttachmentSvc,
    tickets:TicketSvc,
    comments:CommentSvc,
    perms:Perms,
    client:ClientInfo,
)->None:
    attachment= await attachments.require_by_id(attachment_id)
    await _ticket_for_attachment(attachment, tickets, comments, perms)
    if attachment.uploaded_by !=perms.user.id and not perms.is_admin:
        raise PermissionDenied("You can only delete files you uploaded")
    
    await attachments.delete(
        attachment, actor=perms.user, ip_address=client["ip_address"]
    )

