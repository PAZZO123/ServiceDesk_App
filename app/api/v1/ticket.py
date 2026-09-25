import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ClientInfo, DbSession, Perms
from app.core.exceptions import TicketNotFound
from app.models.ticket import Ticket
from app.schemas.comment import CommentCreate
from app.schemas.common import Page, PaginationParams
from app.schemas.ticket import (AssignRequest, StatusChange, TagsUpdate,
                                TicketCreate, TicketFilters, TicketListItem,
                                TicketRead, TicketUpdate)
from app.services.comment_service import CommentService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _service(db: DbSession) -> TicketService:
    return TicketService(db)


TicketSvc = Annotated[TicketService, Depends(_service)]
def _comment_service(db:DbSession)->CommentService:
    return CommentService(db)
CommentSvc=Annotated[CommentService, Depends(_comment_service)]

@router.get(
    "",
    response_model=Page[TicketListItem],
    summary="List tickets",
)
async def list_tickets(
    svc: TicketSvc,
    perms: Perms,
    filters: Annotated[TicketFilters, Depends()],
    pagination: Annotated[PaginationParams, Depends()],
) -> Page[TicketListItem]:
    tickets, total = await svc.list_tickets(
        filters,
        pagination,
        extra_conditions=perms.visibility_conditions(),
    )
    return Page.create(
        items=[TicketListItem.model_validate(t) for t in tickets],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/feed",
    response_model=dict,
    summary="List tickets with cursor pagination",
)
async def ticket_feed(
    svc: TicketSvc,
    perms: Perms,
    filters: Annotated[TicketFilters, Depends()],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    tickets, next_cursor = await svc.list_tickets_cursor(
        filters,
        limit=limit,
        cursor=cursor,
        extra_conditions=perms.visibility_conditions(),
    )

    return {
        "items": [
            TicketListItem.model_validate(t).model_dump(mode="json") for t in tickets
        ],
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/reference/{reference}",
    response_model=TicketRead,
    summary="Look up a ticket by its reference",
)
async def get_by_reference(
    reference: str,
    svc: TicketSvc,
    perms: Perms,
) -> Ticket:
    ticket = await svc.get_by_reference(reference)
    if ticket is None or not perms.can_view(ticket):
        raise TicketNotFound()

    return ticket


@router.get(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Get one ticket",
    responses={404: {"description": "No such ticket, or not visible to you"}},
)
async def get_ticket(
    ticket_id: uuid.UUID,
    svc: TicketSvc,
    perms: Perms,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)
    perms.require_view(ticket)  # raises 404, never 403
    return ticket


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Raise a ticket",
)
async def create_ticket(
    data: TicketCreate,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
) -> Ticket:
  
    return await svc.create(
        data,
        requester=perms.user,
        ip_address=client["ip_address"],
    )


@router.patch(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Update a ticket",
    responses={
        403: {"description": "You may not edit this ticket, or not this field"},
        404: {"description": "No such ticket, or not visible to you"},
    },
)
async def update_ticket(
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)
    perms.require_edit(ticket)
    perms.require_fields(ticket, set(data.model_dump(exclude_unset=True)))

    return await svc.update(ticket, data, actor=perms.user, ip_address=client["ip_address"])


@router.post(
    "/{ticket_id}/status",
    response_model=TicketRead,
    summary="Change a ticket's status",
    responses={
        403: {"description": "Your role may not make this transition"},
        409: {"description": "That transition is not allowed from here"},
    },
)
async def change_status(
    ticket_id: uuid.UUID,
    data: StatusChange,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
    comments:CommentSvc,
) -> Ticket:
     ticket = await svc.require_by_id(ticket_id)
     perms.require_status_change(ticket, data.status)

     original_status = ticket.status

     if data.comment:
            await comments.create(
                ticket,
                CommentCreate(body=data.comment, is_internal=False),
                author=perms.user,
                perms=perms,
                ip_address=client["ip_address"],
                commit=False,
            )

     updated = await svc.change_status(
            ticket, data.status, actor=perms.user, ip_address=client["ip_address"]
        )

     if data.comment and data.status == original_status:
            await svc.db.commit()

     return updated

@router.post(
    "/{ticket_id}/assign",
    response_model=TicketRead,
    summary="Assign a ticket to an agent",
    responses={
        400: {"description": "That user cannot own this ticket"},
        403: {"description": "Only support staff can assign tickets"},
    },
)
async def assign_ticket(
    ticket_id: uuid.UUID,
    data: AssignRequest,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)
    perms.require_assign(ticket)
    return await svc.assign(
        ticket,
        data.assignee_id,
        actor=perms.user,
        ip_address=client["ip_address"],
    )


@router.post(
    "/{ticket_id}/claim",
    response_model=TicketRead,
    summary="Take a ticket for yourself",
)
async def claim_ticket(
    ticket_id: uuid.UUID,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)
    perms.require_assign(ticket)

    return await svc.assign(
        ticket,
        perms.user.id,
        actor=perms.user,
        ip_address=client["ip_address"],
    )


@router.put(
    "/{ticket_id}/tags",
    response_model=TicketRead,
    summary="Set a ticket's tags",
)
async def set_tags(
    ticket_id: uuid.UUID,
    data: TagsUpdate,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)
    perms.require_assign(ticket)

    return await svc.set_tags(
        ticket,
        data.tag_ids,
        actor=perms.user,
        ip_address=client["ip_address"],
    )


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ticket",
    responses={403: {"description": "Only an administrator can delete a ticket"}},
)
async def delete_ticket(
    ticket_id: uuid.UUID,
    svc: TicketSvc,
    perms: Perms,
    client: ClientInfo,
) -> None:
    ticket = await svc.require_by_id(ticket_id)
    perms.require_delete(ticket)
    await svc.soft_delete(ticket, actor=perms.user, ip_address=client["ip_address"])