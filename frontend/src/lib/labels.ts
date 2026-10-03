import type { NotificationType, TicketPriority, TicketStatus } from "../api/types";

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting: "Waiting",
  resolved: "Resolved",
  closed: "Closed",
};

export const PRIORITY_LABEL: Record<TicketPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const STATUSES: TicketStatus[] = ["open", "in_progress", "waiting", "resolved", "closed"];
export const PRIORITIES: TicketPriority[] = ["low", "medium", "high", "urgent"];

// Copy of ALLOWED_TRANSITIONS in app/services/ticket_service.py: which
// status a ticket may move to next. The server enforces it (409).
export const NEXT_STATUSES: Record<TicketStatus, TicketStatus[]> = {
  open: ["in_progress", "waiting", "resolved", "closed"],
  in_progress: ["open", "waiting", "resolved"],
  waiting: ["open", "in_progress", "resolved"],
  resolved: ["closed", "in_progress"],
  closed: [],
};

export const NOTIFICATION_LABEL: Record<NotificationType, string> = {
  ticket_assigned: "New ticket for you",
  ticket_status_changed: "Status changed",
  comment_added: "New comment",
  sla_breached: "SLA breached",
  ticket_mentioned: "You were mentioned",
};
