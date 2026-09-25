import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDenied, TicketNotFound
from app.models.enums import TicketStatus, UserRole
from app.models.team import TeamMembership
from app.models.ticket import Comment, Ticket
from app.models.user import User

REQUESTER_EDITABLE_STATES:frozenset[TicketStatus]=frozenset(
    {TicketStatus.OPEN, TicketStatus.WAITING}
)

REQUESTER_EDITABLE_FIELDS:frozenset[str]=frozenset(
    {
        "title", "description", "extra_data"
    }
)
REQUESTER_STATUS_TARGETS:frozenset[TicketStatus]=frozenset({TicketStatus.CLOSED})
async def load_team_ids(db:AsyncSession, user:User)->frozenset[uuid.UUID]:
    if user.role == UserRole.REQUESTER:
        return frozenset()
    rows= await db.scalars(
        select(TeamMembership.team_id).where(TeamMembership.user_id == user.id)
        
    )
    return frozenset(rows)

@dataclass(frozen=True)
class TicketPermissions:
    user:User
    team_ids:frozenset[uuid.UUID]
    
    @property
    def is_admin(self) ->bool:
        return self.user.role == UserRole.ADMIN
    @property
    def is_staff(self) -> bool:
   
        return self.user.role in (UserRole.AGENT, UserRole.ADMIN)
    def visibility_conditions(self)->list:
        if self.is_admin:
            return []
        clauses=[Ticket.requester_id == self.user.id]
        if self.is_staff:
            clauses.append(Ticket.assignee_id == self.user.id)
            if self.team_ids:
                clauses.append(Ticket.team_id.in_(self.team_ids))
        return [or_(*clauses)]
    
    def can_view(self, ticket: Ticket) -> bool:
         
        if self.is_admin:
            return True

        if ticket.requester_id == self.user.id:
            return True

        if self.is_staff:
            return (
                ticket.assignee_id == self.user.id
                or ticket.team_id in self.team_ids
            )

        return False
    
    def can_edit(self, ticket:Ticket)->bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True
        
        return(
            ticket.requester_id == self.user.id
            and ticket.status in REQUESTER_EDITABLE_STATES
        )
        
    def editable_fields(self, ticket:Ticket)->frozenset[str]|None:
        if self.is_staff:
            return None
        return REQUESTER_EDITABLE_FIELDS
    
    def can_change_status(self, ticket:Ticket, new_status:TicketStatus)->bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True
        return (
           ticket.requester_id == self.user.id
            and new_status in REQUESTER_STATUS_TARGETS
        )
        
    def can_assign(self, ticket:Ticket)->bool:
        return self.is_staff and self.can_view(ticket)
    
    def can_delete(self, ticket:Ticket)->bool:
        return  self.is_admin
    
    #Comments
  
    def comment_conditions(self) -> list:
        if self.is_staff:
            return []
        return [Comment.is_internal.is_(False)]

    def can_see_comment(self, comment: Comment) -> bool:
        return self.is_staff or not comment.is_internal

    def can_post_internal_note(self) -> bool:
        return self.is_staff

    def can_edit_comment(self, comment: Comment) -> bool:
        return comment.author_id == self.user.id

    def can_delete_comment(self, comment: Comment) -> bool:
        return comment.author_id == self.user.id or self.is_admin
    def require_view(self, ticket:Ticket)->None:
        if not self.can_view(ticket):
            raise TicketNotFound()
        
    def require_edit(self, ticket:Ticket)->None:
        self.require_view(ticket)
        if not self.can_edit(ticket):
            raise PermissionDenied(
                " You cannot edit this ticket in its current state."
            )
    def require_fields(self, ticket:Ticket, fields:set[str])->None:
        allowed =self.editable_fields(ticket)
        if allowed is None:
            return
        forbidden=fields -allowed
        if forbidden:
           raise PermissionDenied(
                "You may not change: " + ", ".join(sorted(forbidden)) + "."
            )
            
    def require_status_change(
        self, ticket:Ticket, new_status:TicketStatus
    )->None:
        self.require_view(ticket)
        if not self.can_change_status(ticket, new_status):
            raise PermissionDenied(
                f"You may not move this ticket to {new_status.value}"
            )
    
    def  require_assign(self, ticket:Ticket)->None:
        self.require_view(ticket)
        if not self.can_assign(ticket):
            raise PermissionDenied("Only support staff can assign tickets.")
        
    def require_delete(self, ticket:Ticket)->None:
        self.require_view(ticket)
        if not self.can_delete(ticket):
            raise PermissionDenied("Only an administrator can delete a ticket.")
        
    def can_comment(self, ticket: Ticket) -> bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True
        return ticket.status != TicketStatus.CLOSED
    
    def require_comment(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_comment(ticket):
            raise PermissionDenied(
                "This ticket is closed. Please raise a new one."
            )
        