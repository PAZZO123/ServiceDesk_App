// One typed function per backend endpoint. Pages never build URLs by hand.
import { api, apiRaw } from "./client";
import type {
  AttachmentRead,
  CategoryBrief,
  CommentPage,
  CommentRead,
  MemberRead,
  MemberRemoved,
  Message,
  NotificationItem,
  NotificationPage,
  PermissionCode,
  PermissionRead,
  Readiness,
  RegisterResponse,
  RoleRead,
  SortOrder,
  TeamBrief,
  TeamRole,
  TeamSlaStats,
  TicketCreate,
  TicketFeedPage,
  TicketPage,
  TicketPriority,
  TicketRead,
  TicketSortField,
  TicketStatus,
  TicketUpdate,
  TokenPair,
  UnreadCount,
  User,
  UserCreate,
  UserPage,
  UserProfileUpdate,
  UserRead,
} from "./types";

// Turns {a: 1, b: undefined, c: ""} into "a=1": empty filters are left out.
function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

// Saves a fetched file. The download needs our Authorization header, so a
// plain <a href> cannot be used: we fetch it as a blob and click a link.
async function saveResponse(res: Response, fallbackName: string): Promise<void> {
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(disposition);
  const name = match ? decodeURIComponent(match[1] ?? match[2]) : fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  // Revoke a moment later: Firefox needs the URL alive while it starts.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ----------------------------------------------------------------- auth

export function login(email: string, password: string): Promise<TokenPair> {
  const form = new URLSearchParams({ username: email, password });
  return api<TokenPair>("/auth/login", { method: "POST", body: form, auth: false });
}

export function logout(refreshToken: string): Promise<Message> {
  return api<Message>("/auth/logout", {
    method: "POST",
    json: { refresh_token: refreshToken },
    auth: false,
  });
}

export function register(data: UserCreate): Promise<RegisterResponse> {
  return api<RegisterResponse>("/auth/register", { method: "POST", json: data, auth: false });
}

export function verifyEmail(token: string): Promise<Message> {
  return api<Message>("/auth/verify-email", { method: "POST", json: { token }, auth: false });
}

export function resendVerification(email: string): Promise<Message> {
  return api<Message>("/auth/resend-verification", {
    method: "POST",
    json: { email },
    auth: false,
  });
}

export function requestPasswordReset(email: string): Promise<Message> {
  return api<Message>("/auth/password-reset", { method: "POST", json: { email }, auth: false });
}

export function confirmPasswordReset(
  token: string,
  newPassword: string,
  confirmPassword: string,
): Promise<Message> {
  return api<Message>("/auth/password-reset/confirm", {
    method: "POST",
    json: { token, new_password: newPassword, confirm_password: confirmPassword },
    auth: false,
  });
}

export function getMe(): Promise<User> {
  return api<User>("/auth/me");
}

export function updateMe(fullName: string): Promise<User> {
  return api<User>("/auth/me", { method: "PATCH", json: { full_name: fullName } });
}

export function updateMyProfile(data: UserProfileUpdate): Promise<User> {
  return api<User>("/auth/me/profile", { method: "PATCH", json: data });
}

export function changePassword(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
): Promise<Message> {
  return api<Message>("/auth/change-password", {
    method: "POST",
    json: {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    },
  });
}

// --------------------------------------------------------------- system

export async function getReadiness(): Promise<Readiness> {
  // /health/ready answers 503 with the same body when the DB is down, so
  // read the body ourselves instead of treating 503 as an exception.
  const res = await fetch("/health/ready");
  return (await res.json()) as Readiness;
}

// -------------------------------------------------------------- catalog

export function listCategories(): Promise<CategoryBrief[]> {
  return api<CategoryBrief[]>("/categories");
}

export function listTeams(): Promise<TeamBrief[]> {
  return api<TeamBrief[]>("/teams");
}

// -------------------------------------------------------------- tickets

export type TicketFilters = {
  status?: TicketStatus;
  priority?: TicketPriority;
  category_id?: string;
  team_id?: string;
  assignee_id?: string;
  requester_id?: string;
  unassigned?: boolean;
  sla_breached?: boolean;
  // Resolved at some point and still resolved or closed (closing keeps it).
  resolved?: boolean;
  created_after?: string;
  created_before?: string;
  q?: string;
  sort?: TicketSortField;
  order?: SortOrder;
};

export function listTickets(
  filters: TicketFilters & { page?: number; size?: number },
): Promise<TicketPage> {
  return api<TicketPage>(`/tickets${query(filters)}`);
}

export function ticketFeed(limit: number, cursor?: string | null): Promise<TicketFeedPage> {
  return api<TicketFeedPage>(`/tickets/feed${query({ limit, cursor })}`);
}

export function getTicket(id: string): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}`);
}

export function getTicketByReference(reference: string): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/reference/${encodeURIComponent(reference.trim())}`);
}

export function createTicket(data: TicketCreate): Promise<TicketRead> {
  return api<TicketRead>("/tickets", { method: "POST", json: data });
}

export function updateTicket(id: string, data: TicketUpdate): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}`, { method: "PATCH", json: data });
}

export function deleteTicket(id: string): Promise<void> {
  return api<void>(`/tickets/${id}`, { method: "DELETE" });
}

export function changeStatus(
  id: string,
  status: TicketStatus,
  comment?: string,
): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}/status`, {
    method: "POST",
    json: { status, comment: comment || null },
  });
}

export function assignTicket(id: string, assigneeId: string | null): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}/assign`, {
    method: "POST",
    json: { assignee_id: assigneeId },
  });
}

export function claimTicket(id: string): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}/claim`, { method: "POST" });
}

export function setTicketTags(id: string, tagIds: string[]): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}/tags`, { method: "PUT", json: { tag_ids: tagIds } });
}

export async function exportTicketsCsv(filters: TicketFilters): Promise<void> {
  const res = await apiRaw(`/exports/tickets.csv${query(filters)}`);
  await saveResponse(res, "tickets.csv");
}

// ------------------------------------------------------------- comments

export function listComments(ticketId: string): Promise<CommentPage> {
  return api<CommentPage>(`/tickets/${ticketId}/comments?size=100`);
}

export function addComment(
  ticketId: string,
  body: string,
  isInternal: boolean,
): Promise<CommentRead> {
  return api<CommentRead>(`/tickets/${ticketId}/comments`, {
    method: "POST",
    json: { body, is_internal: isInternal },
  });
}

export function editComment(commentId: string, body: string): Promise<CommentRead> {
  return api<CommentRead>(`/comments/${commentId}`, { method: "PATCH", json: { body } });
}

export function deleteComment(commentId: string): Promise<void> {
  return api<void>(`/comments/${commentId}`, { method: "DELETE" });
}

// ---------------------------------------------------------- attachments

function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export function listAttachments(ticketId: string): Promise<AttachmentRead[]> {
  return api<AttachmentRead[]>(`/tickets/${ticketId}/attachments`);
}

export function uploadTicketAttachment(ticketId: string, file: File): Promise<AttachmentRead> {
  return api<AttachmentRead>(`/tickets/${ticketId}/attachments`, {
    method: "POST",
    body: fileForm(file),
  });
}

export function uploadCommentAttachment(commentId: string, file: File): Promise<AttachmentRead> {
  return api<AttachmentRead>(`/comments/${commentId}/attachments`, {
    method: "POST",
    body: fileForm(file),
  });
}

export async function downloadAttachment(attachment: AttachmentRead): Promise<void> {
  const res = await apiRaw(`/attachments/${attachment.id}/download`);
  await saveResponse(res, attachment.original_filename);
}

export function deleteAttachment(attachmentId: string): Promise<void> {
  return api<void>(`/attachments/${attachmentId}`, { method: "DELETE" });
}

// --------------------------------------------------------- notifications

export function listNotifications(
  page: number,
  size: number,
  unreadOnly: boolean,
): Promise<NotificationPage> {
  return api<NotificationPage>(`/notifications${query({ page, size, unread_only: unreadOnly })}`);
}

export function getUnreadCount(): Promise<UnreadCount> {
  return api<UnreadCount>("/notifications/unread-count");
}

export function markNotificationRead(id: string): Promise<NotificationItem> {
  return api<NotificationItem>(`/notifications/${id}/read`, { method: "POST" });
}

export function markAllNotificationsRead(): Promise<void> {
  return api<void>("/notifications/read-all", { method: "POST" });
}

// ---------------------------------------------------------------- teams

export function listMembers(teamId: string): Promise<MemberRead[]> {
  return api<MemberRead[]>(`/teams/${teamId}/members`);
}

export function addMember(teamId: string, userId: string, role: TeamRole): Promise<MemberRead> {
  return api<MemberRead>(`/teams/${teamId}/members`, {
    method: "POST",
    json: { user_id: userId, role_in_team: role },
  });
}

export function setMemberRole(teamId: string, userId: string, role: TeamRole): Promise<MemberRead> {
  return api<MemberRead>(`/teams/${teamId}/members/${userId}`, {
    method: "PATCH",
    json: { role_in_team: role },
  });
}

export function removeMember(teamId: string, userId: string): Promise<MemberRemoved> {
  return api<MemberRemoved>(`/teams/${teamId}/members/${userId}`, { method: "DELETE" });
}

// --------------------------------------------------------- users, roles

export function listUsers(page: number, size: number): Promise<UserPage> {
  return api<UserPage>(`/users${query({ page, size })}`);
}

export function assignRole(userId: string, role: string): Promise<UserRead> {
  return api<UserRead>(`/users/${userId}/role`, { method: "PATCH", json: { role } });
}

export function listRoles(): Promise<RoleRead[]> {
  return api<RoleRead[]>("/roles");
}

export function listPermissions(): Promise<PermissionRead[]> {
  return api<PermissionRead[]>("/permissions");
}

export function createRole(
  name: string,
  description: string,
  permissions: PermissionCode[],
): Promise<RoleRead> {
  return api<RoleRead>("/roles", {
    method: "POST",
    json: { name, description: description || null, permissions },
  });
}

export function setRolePermissions(roleId: string, permissions: PermissionCode[]): Promise<RoleRead> {
  return api<RoleRead>(`/roles/${roleId}/permissions`, {
    method: "PUT",
    json: { permissions },
  });
}

export function deleteRole(roleId: string): Promise<void> {
  return api<void>(`/roles/${roleId}`, { method: "DELETE" });
}

// ------------------------------------------------------------ analytics

export function teamSla(days: number): Promise<TeamSlaStats[]> {
  return api<TeamSlaStats[]>(`/analytics/teams${query({ days })}`);
}
