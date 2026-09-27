from enum import StrEnum


class SystemRole(StrEnum):
    REQUESTER = "requester"
    AGENT = "agent"
    OBSERVER = "observer"
    ADMIN = "admin"


class Permission(StrEnum):
    TICKET_VIEW_ALL = "ticket.view_all"
    TICKET_WORK = "ticket.work"
    TICKET_DELETE = "ticket.delete"
    TICKET_STARTS_HIGH = "ticket.starts_high"
    COMMENT_READ_INTERNAL = "comment.read_internal"
    CONTENT_MODERATE = "content.moderate"
    TEAM_MANAGE = "team.manage"
    USER_MANAGE = "user.manage"


class TicketOwnerRole(StrEnum):
    REQUESTER = "requester"
    ASSIGNEE = "assignee"
    WATCHER = "watcher"


class TeamRole(StrEnum):
    MEMBER = "member"
    LEAD = "lead"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(StrEnum):
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    COMMENT_ADDED = "comment_added"
    SLA_BREACHED = "sla_breached"
    TICKET_MENTIONED = "ticket_mentioned"

