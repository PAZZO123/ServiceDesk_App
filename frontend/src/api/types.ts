import type { components } from "./schema";

// Short names over the generated OpenAPI types (npm run gen:api).
type Schemas = components["schemas"];

export type TokenPair = Schemas["TokenPair"];
export type Message = Schemas["Message"];

export type User = Schemas["UserWithProfile"];
export type UserRead = Schemas["UserRead"];
export type UserPublic = Schemas["UserPublic"];
export type UserCreate = Schemas["UserCreate"];
export type UserProfileUpdate = Schemas["UserProfileUpdate"];
export type RegisterResponse = Schemas["RegisterResponse"];
export type UserPage = Schemas["Page_UserRead_"];

export type Role = Schemas["RoleBrief"];
export type RoleRead = Schemas["RoleRead"];
export type RoleCreate = Schemas["RoleCreate"];
export type PermissionRead = Schemas["PermissionRead"];
export type PermissionCode = Schemas["Permission"];

export type TicketStatus = Schemas["TicketStatus"];
export type TicketPriority = Schemas["TicketPriority"];
export type TicketSortField = Schemas["TicketSortField"];
export type SortOrder = Schemas["SortOrder"];
export type TicketListItem = Schemas["TicketListItem"];
export type TicketRead = Schemas["TicketRead"];
export type TicketCreate = Schemas["TicketCreate"];
export type TicketUpdate = Schemas["TicketUpdate"];
export type TicketPage = Schemas["Page_TicketListItem_"];
export type TagBrief = Schemas["TagBrief"];

export type CategoryBrief = Schemas["CategoryBrief"];
export type TeamBrief = Schemas["TeamBrief"];
export type TeamRole = Schemas["TeamRole"];
export type MemberRead = Schemas["MemberRead"];

export type CommentRead = Schemas["CommentRead"];
export type CommentPage = Schemas["Page_CommentRead_"];
export type AttachmentRead = Schemas["AttachmentRead"];

// "NotificationItem", not "Notification": that name is a browser global.
export type NotificationItem = Schemas["NotificationRead"];
export type NotificationPage = Schemas["Page_NotificationRead_"];
export type NotificationType = Schemas["NotificationType"];
export type UnreadCount = Schemas["UnreadCount"];

export type TeamSlaStats = Schemas["TeamSlaStats"];

// GET /tickets/feed is typed as a plain dict on the server, so we spell
// out what it really returns (app/api/v1/ticket.py, ticket_feed).
export type TicketFeedPage = {
  items: TicketListItem[];
  next_cursor: string | null;
  has_more: boolean;
};

// DELETE /teams/{id}/members/{user_id} returns a plain dict as well.
export type MemberRemoved = { removed: boolean; open_tickets_still_assigned: number };

export type Readiness = {
  status: "ready" | "not_ready";
  checks: { database: "ok" | "unreachable" };
};
