
import { api, apiRaw } from "./client";
import type {
  AttachmentRead,
  CategoryBrief,
  CommentPage,
  CommentRead,
  TicketCreate,
  TicketPage,
  TicketRead,
  TicketStatus,
  TokenPair,
  User,
} from "./types";

export function login(email: string, password: string): Promise<TokenPair> {
  const form = new URLSearchParams({ username: email, password });
  return api<TokenPair>("/auth/login", { method: "POST", body: form, auth: false });
}
export function logout(refreshToken: string): Promise<void> {
  return api<void>("/auth/logout", {
    method: "POST",
    json: { refresh_token: refreshToken },
    auth: false,
  });
}

export function getMe(): Promise<User> {
  return api<User>("/auth/me");
}


export type TicketQuery = {
  page?: number;
  size?: number;
  status?: TicketStatus;
  q?: string;
};

// Tickets
export function listTickets(query: TicketQuery): Promise<TicketPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  return api<TicketPage>(`/tickets?${params}`);
}

export function getTicket(id: string): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}`);
}

export function createTicket(data: TicketCreate): Promise<TicketRead> {
  return api<TicketRead>("/tickets", { method: "POST", json: data });
}

export function changeStatus(
  id: string,
  status: TicketStatus,
  comment?: string,
): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}/status`, {
    method: "POST",
    json: { status, comment },
  });
}

export function claimTicket(id: string): Promise<TicketRead> {
  return api<TicketRead>(`/tickets/${id}/claim`, { method: "POST" });
}

export function listCategories(): Promise<CategoryBrief[]> {
  return api<CategoryBrief[]>("/categories");
}

// ------------------------------------------------------------ comments

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

//  attachments

export function listAttachments(ticketId: string): Promise<AttachmentRead[]> {
  return api<AttachmentRead[]>(`/tickets/${ticketId}/attachments`);
}

export function uploadAttachment(ticketId: string, file: File): Promise<AttachmentRead> {
  const form = new FormData();
  form.append("file", file);
  return api<AttachmentRead>(`/tickets/${ticketId}/attachments`, {
    method: "POST",
    body: form,
  });
}
export async function downloadAttachment(attachment: AttachmentRead): Promise<void> {
  const res = await apiRaw(`/attachments/${attachment.id}/download`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = attachment.original_filename;
  link.click();

  URL.revokeObjectURL(url);
}