import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status 
from app.api.deps import ClientInfo, DbSession, VerifiedUser
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import Page, PaginationParams
from app.models.ticket import Ticket
from app.core.exceptions import TicketNotFound

from app.schemas.ticket import (
    StatusChange,
    TicketFilters,
    TicketCreate,
    TicketListItem,
    TicketRead,
    TicketUpdate,
)

from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets"])

#Temporary Visibility Rule
def _visibility_condition(user: User)-> list:
    if user.role == UserRole.REQUESTER:
        return [Ticket.requester_id == user.id]
    return[]

def _may_see(ticket:Ticket, user:User)->bool:
       if user.role != UserRole.REQUESTER:
            return True
       return ticket.requester_id == user.id
   
def _service(db: DbSession)->TicketService:
    return TicketService(db)
TicketSvc=Annotated[TicketService, Depends(_service)]


#List
@router.get(
    "",
    response_model=Page[TicketListItem],
    summary="list tickets"
)
async def list_tickets(
    svc: TicketSvc,
    user:VerifiedUser,
    filters:Annotated[TicketFilters, Depends()],
    pagination: Annotated[PaginationParams, Depends()]
)->Page[TicketListItem]:
    tickets, total= await svc.list_tickets(
        filters,
        pagination,
        extra_conditions=_visibility_condition(user)
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
    user: VerifiedUser,
    filters: Annotated[TicketFilters, Depends()],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    tickets, next_cursor = await svc.list_tickets_cursor(
        filters,
        limit=limit,
        cursor=cursor,
        extra_conditions=_visibility_condition(user),
    )

    return {
        "items": [TicketListItem.model_validate(t).model_dump(mode="json") for t in tickets],
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
    user: VerifiedUser,
) -> Ticket:
    ticket = await svc.get_by_reference(reference)

    if ticket is None or not _may_see(ticket, user):

        raise TicketNotFound()

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
    user: VerifiedUser,
    client: ClientInfo,
) -> Ticket:
    return await svc.create(
        data,
        requester=user,
        ip_address=client["ip_address"],
    )
    
@router.get(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Get one ticket",
)
async def get_ticket(
    ticket_id: uuid.UUID,
    svc: TicketSvc,
    user: VerifiedUser,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)

    if not _may_see(ticket, user):
        from app.core.exceptions import TicketNotFound

        raise TicketNotFound()

    return ticket

@router.patch(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Update a ticket",
)
async def update_ticket(
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    svc: TicketSvc,
    user: VerifiedUser,
    client: ClientInfo,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)

    if not _may_see(ticket, user):
        from app.core.exceptions import TicketNotFound

        raise TicketNotFound()

    return await svc.update(
        ticket, data, actor=user, ip_address=client["ip_address"]
    )

@router.post(
    "/{ticket_id}/status",
    response_model=TicketRead,
    summary="Change a ticket's status",
    responses={409: {"description": "That transition is not allowed"}},
)
async def change_status(
    ticket_id: uuid.UUID,
    data: StatusChange,
    svc: TicketSvc,
    user: VerifiedUser,
    client: ClientInfo,
) -> Ticket:
    ticket = await svc.require_by_id(ticket_id)

    if not _may_see(ticket, user):
        from app.core.exceptions import TicketNotFound

        raise TicketNotFound()

    return await svc.change_status(
        ticket, data.status, actor=user, ip_address=client["ip_address"]
    )
    
@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ticket"
)
async def delete_ticket(
    ticket_id:uuid.UUID,
    svc: TicketSvc,
    user:VerifiedUser,
    client:ClientInfo
)->None:
    ticket= await svc.require_by_id(ticket_id)
    if not _may_see(ticket, user):
        raise TicketNotFound()
    await svc.soft_delete(ticket, actor=user, ip_address=client["ip_address"])