from enum import Enum


class UserRole(str, Enum):
    REQUESTER="requester"
    AGENT="agent"
    ADMIN="admin"
    
class TeamRole(str, Enum):
    MEMBER="member"
    LEAD="lead"
    
    
class TicketStatus(str, Enum):
    OPEN="open"
    IN_PROGRESS="in_progress"
    WAITING="waiting"
    RESOLVEd="resolved"
    CLOSED="closed"
    
    
class TicketPriority(str, Enum):
    LOW="low"
    MEDIUM="medium"
    HIGH="high"
    URGENT="urgent"
    
class NotificationType(str, Enum):
    TICKET_ASSIGNED="ticket_assigned"
    TICKET_STATUS_CHANGED="ticket_status_changed"
    COMMENT_ADDED="comment_added"
    SLA_BREACHED="sla_breached"
    TICKET_MENTIONED="ticket_mentioned"