
import type { components } from "./schema";

type Schemas = components["schemas"];

export type TokenPair = Schemas["TokenPair"];
export type User = Schemas["UserWithProfile"];
export type Role = Schemas["RoleBrief"];

export type TicketStatus = Schemas["TicketStatus"];
export type TicketPriority = Schemas["TicketPriority"];
export type TicketListItem = Schemas["TicketListItem"];
export type TicketRead = Schemas["TicketRead"];
export type TicketCreate = Schemas["TicketCreate"];
export type TicketPage = Schemas["Page_TicketListItem_"];
export type CategoryBrief = Schemas["CategoryBrief"];

export type CommentRead = Schemas["CommentRead"];
export type CommentPage = Schemas["Page_CommentRead_"];
export type AttachmentRead = Schemas["AttachmentRead"];
export type NotificationItem = Schemas["NotificationRead"];
export type NotificationPage = Schemas["Page_NotificationRead_"];
export type UnreadCount = Schemas["UnreadCount"];