import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDenied, TicketNotFound
from app.models.enums import Permission, TicketOwnerRole, TicketStatus
from app.models.team import TeamMembership
from app.models.ticket import Comment, Ticket, TicketOwner
from app.models.user import User

REQUESTER_EDITABLE_STATES: frozenset[TicketStatus] = frozenset(
    {TicketStatus.OPEN, TicketStatus.WAITING}
)

REQUESTER_EDITABLE_FIELDS: frozenset[str] = frozenset(
    {"title", "description", "extra_data"}
)
REQUESTER_STATUS_TARGETS: frozenset[TicketStatus] = frozenset({TicketStatus.CLOSED})


async def load_team_ids(db: AsyncSession, user: User) -> frozenset[uuid.UUID]:
    if not user.role.grants(Permission.TICKET_WORK):
        return frozenset()
    rows = await db.scalars(
        select(TeamMembership.team_id).where(TeamMembership.user_id == user.id)
    )
    return frozenset(rows)


@dataclass(frozen=True)
class TicketPermissions:
    user: User
    team_ids: frozenset[uuid.UUID]

    def has(self, permission: Permission) -> bool:
        return self.user.role.grants(permission)

    @property
    def is_staff(self) -> bool:
        return self.has(Permission.TICKET_WORK)

    @property
    def sees_all_tickets(self) -> bool:
        return self.has(Permission.TICKET_VIEW_ALL)

    @property
    def reads_internal_notes(self) -> bool:
        return self.has(Permission.COMMENT_READ_INTERNAL)

    @property
    def can_moderate_content(self) -> bool:
        return self.has(Permission.CONTENT_MODERATE)

    # SQL half - must say the same thing as can_view()
    def visibility_conditions(self) -> list:
        if self.sees_all_tickets:
            return []
        clauses = [
            Ticket.id.in_(
                select(TicketOwner.ticket_id).where(TicketOwner.user_id == self.user.id)
            )
        ]
        if self.is_staff and self.team_ids:
            clauses.append(Ticket.team_id.in_(self.team_ids))
        return [or_(*clauses)]

    def can_view(self, ticket: Ticket) -> bool:
        if self.sees_all_tickets:
            return True

        if ticket.has_owner(self.user.id):
            return True

        return self.is_staff and ticket.team_id in self.team_ids

    def can_edit(self, ticket: Ticket) -> bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True

        return (
            ticket.has_owner(self.user.id, TicketOwnerRole.REQUESTER)
            and ticket.status in REQUESTER_EDITABLE_STATES
        )

    def can_set_priority(self) -> bool:
        return self.is_staff

    def editable_fields(self, ticket: Ticket) -> frozenset[str] | None:
        if self.is_staff:
            return None
        return REQUESTER_EDITABLE_FIELDS

    def can_change_status(self, ticket: Ticket, new_status: TicketStatus) -> bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True
        return (
            ticket.has_owner(self.user.id, TicketOwnerRole.REQUESTER)
            and new_status in REQUESTER_STATUS_TARGETS
        )

    def can_assign(self, ticket: Ticket) -> bool:
        return self.is_staff and self.can_view(ticket)

    def can_delete(self, ticket: Ticket) -> bool:
        return self.has(Permission.TICKET_DELETE)

    # Seeing a ticket is not the same as taking part: observers and watchers only read.
    def can_comment(self, ticket: Ticket) -> bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True
        return (
            ticket.has_owner(self.user.id, TicketOwnerRole.REQUESTER)
            and ticket.status != TicketStatus.CLOSED
        )

    # Comments
    def comment_conditions(self) -> list:
        if self.reads_internal_notes:
            return []
        return [Comment.is_internal.is_(False)]

    def can_see_comment(self, comment: Comment) -> bool:
        return self.reads_internal_notes or not comment.is_internal

    def can_post_internal_note(self) -> bool:
        return self.is_staff

    def can_edit_comment(self, comment: Comment) -> bool:
        return comment.author_id == self.user.id

    def can_delete_comment(self, comment: Comment) -> bool:
        return comment.author_id == self.user.id or self.can_moderate_content

    def require_view(self, ticket: Ticket) -> None:
        if not self.can_view(ticket):
            raise TicketNotFound()

    def require_edit(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_edit(ticket):
            raise PermissionDenied(
                "You cannot edit this ticket in its current state."
            )

    def require_fields(self, ticket: Ticket, fields: set[str]) -> None:
        allowed = self.editable_fields(ticket)
        if allowed is None:
            return
        forbidden = fields - allowed
        if forbidden:
            raise PermissionDenied(
                "You may not change: " + ", ".join(sorted(forbidden)) + "."
            )

    def require_status_change(self, ticket: Ticket, new_status: TicketStatus) -> None:
        self.require_view(ticket)
        if not self.can_change_status(ticket, new_status):
            raise PermissionDenied(
                f"You may not move this ticket to {new_status.value}"
            )

    def require_assign(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_assign(ticket):
            raise PermissionDenied("Only support staff can assign tickets.")

    def require_delete(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_delete(ticket):
            raise PermissionDenied("You do not have permission to delete tickets.")

    def require_comment(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_comment(ticket):
            raise PermissionDenied(
                "You cannot comment on this ticket."
            )
