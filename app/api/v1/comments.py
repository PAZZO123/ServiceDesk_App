
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import ClientInfo, DbSession, Perms
from app.core.exceptions import CommentNotFound, PermissionDenied
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate
from app.schemas.common import Page, PaginationParams
from app.services.comment_service import CommentService
from app.services.ticket_service import TicketService

router = APIRouter(tags=["Comments"])


def _comments(db: DbSession) -> CommentService:
    return CommentService(db)


def _tickets(db: DbSession) -> TicketService:
    return TicketService(db)


CommentSvc = Annotated[CommentService, Depends(_comments)]
TicketSvc = Annotated[TicketService, Depends(_tickets)]
@router.get(
    "/tickets/{ticket_id}/comments",
    response_model=Page[CommentRead],
    summary="The conversation on a ticket",
)
async def list_comments(
    ticket_id: uuid.UUID,
    tickets: TicketSvc,
    comments: CommentSvc,
    perms: Perms,
    pagination: Annotated[PaginationParams, Depends()],
) -> Page[CommentRead]:
    ticket = await tickets.require_by_id(ticket_id)
    perms.require_view(ticket)

    items, total = await comments.list_for_ticket(ticket, perms, pagination)

    return Page.create(
        items=[CommentRead.model_validate(c) for c in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment",
    responses={
        400: {"description": "Bad parent comment"},
        403: {"description": "Closed ticket, or internal note by a requester"},
    },
)
async def add_comment(
    ticket_id: uuid.UUID,
    data: CommentCreate,
    tickets: TicketSvc,
    comments: CommentSvc,
    perms: Perms,
    client: ClientInfo,
):
    ticket = await tickets.require_by_id(ticket_id)
    perms.require_comment(ticket)
    
    if data.is_internal and not perms.can_post_internal_note():
        raise PermissionDenied("Only support staff can leave internal notes.")

    return await comments.create(
        ticket,
        data,
        author=perms.user,
        perms=perms,
        ip_address=client["ip_address"],
    )


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentRead,
    summary="Edit your own comment",
)
async def edit_comment(
    comment_id: uuid.UUID,
    data: CommentUpdate,
    tickets: TicketSvc,
    comments: CommentSvc,
    perms: Perms,
    client: ClientInfo,
):
    comment = await comments.require_by_id(comment_id)
    ticket = await tickets.require_by_id(comment.ticket_id)

    if not perms.can_view(ticket) or not perms.can_see_comment(comment):
        raise CommentNotFound()

    if not perms.can_edit_comment(comment):
        raise PermissionDenied("You can only edit your own comments.")

    return await comments.update(
        comment, data, actor=perms.user, ip_address=client["ip_address"]
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_comment(
    comment_id: uuid.UUID,
    tickets: TicketSvc,
    comments: CommentSvc,
    perms: Perms,
    client: ClientInfo,
) -> None:
    comment = await comments.require_by_id(comment_id)
    ticket = await tickets.require_by_id(comment.ticket_id)

    if not perms.can_view(ticket) or not perms.can_see_comment(comment):
        raise CommentNotFound()
    if not perms.can_delete_comment(comment):
        raise PermissionDenied("You cannot delete this comment.")

    await comments.delete(comment, actor=perms.user, ip_address=client["ip_address"])