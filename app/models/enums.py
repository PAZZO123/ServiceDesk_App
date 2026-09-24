from enum import StrEnum


class UserRole(StrEnum):
    REQUESTER = "requester"
    AGENT = "agent"
    ADMIN = "admin"


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
