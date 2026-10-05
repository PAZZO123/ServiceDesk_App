import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDenied, TicketNotFound
from app.models.attachment import Attachment
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
# The work is done: only a moderator may still delete comments and files.
FINISHED_STATES: frozenset[TicketStatus] = frozenset(
    {TicketStatus.RESOLVED, TicketStatus.CLOSED}
)
STAFF_EDITABLE_FIELDS: frozenset[str] = frozenset({"category_id", "priority"})


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
    def editable_fields(self, ticket: Ticket) -> frozenset[str]:
        fields: set[str] = set()
        
        if (
            ticket.has_owner(self.user.id, TicketOwnerRole.REQUESTER)
            and ticket.status in REQUESTER_EDITABLE_STATES
        ):
            fields |= REQUESTER_EDITABLE_FIELDS
        if self.is_staff:
            fields |= STAFF_EDITABLE_FIELDS
        return frozenset(fields)

    def can_change_status(self, ticket: Ticket, new_status: TicketStatus) -> bool:
        if not self.can_view(ticket):
            return False
        if self.is_staff:
            return True
        return (
            ticket.has_owner(self.user.id, TicketOwnerRole.REQUESTER)
            and new_status in REQUESTER_STATUS_TARGETS
        )

    # Closed is final (ALLOWED_TRANSITIONS[CLOSED] is empty): nobody works on
    # it any more, so nobody - not even an admin - assigns, claims or
    # reassigns it. A new problem gets a new ticket.
    def can_assign(self, ticket: Ticket) -> bool:
        if ticket.status == TicketStatus.CLOSED:
            return False
        return self.is_staff and self.can_view(ticket)

    # Tags stay editable on a closed ticket: they are for reporting
    # ("all printer outages this month"), not part of the conversation.
    def can_tag(self, ticket: Ticket) -> bool:
        return self.is_staff and self.can_view(ticket)

    def can_delete(self, ticket: Ticket) -> bool:
        return self.has(Permission.TICKET_DELETE)

    # Seeing a ticket is not the same as taking part: observers and watchers only read.
    # A closed conversation is closed for EVERYONE, staff included (before,
    # only the requester was stopped). Files count as comments too.
    def can_comment(self, ticket: Ticket) -> bool:
        if not self.can_view(ticket) or ticket.status == TicketStatus.CLOSED:
            return False
        if self.is_staff:
            return True
        return ticket.has_owner(self.user.id, TicketOwnerRole.REQUESTER)

    # Comments
    def comment_conditions(self) -> list:
        if self.reads_internal_notes:
            return []
        return [Comment.is_internal.is_(False)]

    def can_see_comment(self, comment: Comment) -> bool:
        return self.reads_internal_notes or not comment.is_internal

    def can_post_internal_note(self) -> bool:
        return self.is_staff

    # Editing your comment (or adding files to it) changes the conversation,
    # so it stops when the ticket is closed - same rule as can_comment.
    def can_edit_comment(self, comment: Comment, ticket: Ticket) -> bool:
        return comment.author_id == self.user.id and ticket.status != TicketStatus.CLOSED
    def can_reassign(self, ticket: Ticket) -> bool:
            assignee = ticket.assignee
            return (
            assignee is None
            or assignee.id == self.user.id
            or self.has(Permission.TICKET_REASSIGN)
        )

    # Once a ticket is resolved or closed, its conversation and files are the
    # record of how it was solved: authors can no longer remove their own
    # messages or files. Only content.moderate (admin) still can, e.g. to
    # remove a password someone pasted. Checked by permission, not role name.
    def _author_may_delete(self, author_id: uuid.UUID, ticket: Ticket) -> bool:
        return author_id == self.user.id and ticket.status not in FINISHED_STATES

    def can_delete_comment(self, comment: Comment, ticket: Ticket) -> bool:
        return self.can_moderate_content or self._author_may_delete(comment.author_id, ticket)

    def can_delete_attachment(self, attachment: Attachment, ticket: Ticket) -> bool:
        return self.can_moderate_content or self._author_may_delete(
            attachment.uploaded_by, ticket
        )

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
        if ticket.status == TicketStatus.CLOSED:
            raise PermissionDenied("This ticket is closed. It cannot be assigned or claimed.")
        if not self.can_assign(ticket):
            raise PermissionDenied("Only support staff can assign tickets.")

    def require_tag(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_tag(ticket):
            raise PermissionDenied("Only support staff can tag tickets.")
        
    def require_reassign(self, ticket: Ticket) -> None:
        if not self.can_reassign(ticket):
            name = ticket.assignee.full_name if ticket.assignee else "Another agent"
            raise PermissionDenied(
                f"{name} is already working on this ticket. "
                "Only an administrator can reassign it."
            )


    def require_delete(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if not self.can_delete(ticket):
            raise PermissionDenied("You do not have permission to delete tickets.")

    def require_comment(self, ticket: Ticket) -> None:
        self.require_view(ticket)
        if ticket.status == TicketStatus.CLOSED:
            raise PermissionDenied(
                "This ticket is closed. Raise a new ticket if the problem returns."
            )
        if not self.can_comment(ticket):
            raise PermissionDenied(
                "You cannot comment on this ticket."
            )
