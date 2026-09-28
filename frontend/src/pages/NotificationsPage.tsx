import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import {
    listNotifications,
    markAllNotificationsRead,
    markNotificationRead,
} from "../api/endpoints";
import type { NotificationItem } from "../api/types";

const PAGE_SIZE = 20;

// Turns one notification into text for the screen.
// We do NOT know exactly what is inside `payload`: on the Python side it is
// dict[str, Any], so the TypeScript type is { [key: string]: unknown }.
// "unknown" forces us to check the type before we use a value. That is
// safer than "any", which would let a wrong guess through.
function describe(n: NotificationItem): { text: string; ticketId: string | null } {
  // "comment_added" -> "comment added"
  const label = n.type.replaceAll("_", " ");

  // Use it only if it really is a string.
  const ticketId = typeof n.payload["ticket_id"] === "string" ? n.payload["ticket_id"] : null;

  // Look for a human-readable field. Take the first one that is a string.
  // `(v): v is string` is a "type guard": it tells TypeScript that after
  // this filter the value is a string, not unknown.
  const extra = ["message", "title", "reference"]
    .map((key) => n.payload[key])
    .find((v): v is string => typeof v === "string");

  return { text: extra ? `${label}: ${extra}` : label, ticketId };
}

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const queryClient = useQueryClient();

  // The query key has page and unreadOnly inside. When either changes,
  // TanStack Query sees a NEW key and fetches again. It starts with
  // "notifications", so the hook's invalidateQueries(["notifications"])
  // matches every page and filter at once.
  const query = useQuery({
    queryKey: ["notifications", page, unreadOnly],
    queryFn: () => listNotifications(page, PAGE_SIZE, unreadOnly),
    // While page 2 loads, keep showing page 1 instead of a blank screen.
    // Same idea as in TicketListPage.
    placeholderData: keepPreviousData,
  });

  // After a change on the server, mark all notification queries as stale
  // so they refetch. (The SSE stream does this too, so it is a second
  // safety net. If the stream is down, the page still updates.)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });

  // useMutation is for writes (POST). useQuery is for reads (GET).
  const readOne = useMutation({ mutationFn: markNotificationRead, onSuccess: refresh });
  const readAll = useMutation({ mutationFn: markAllNotificationsRead, onSuccess: refresh });

  // `?? []` gives an empty list while nothing has loaded yet,
  // so the code below never has to ask "is data undefined?".
  const items = query.data?.items ?? [];
  // Math.max(1, ...) so an empty list still says "Page 1 of 1".
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Notifications</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => {
                setUnreadOnly(e.target.checked);
                setPage(1); // a new filter starts again on page 1
              }}
            />
            Unread only
          </label>
          <button
            className="btn-secondary"
            disabled={readAll.isPending} // stop double clicks while sending
            onClick={() => readAll.mutate()}
          >
            Mark all as read
          </button>
        </div>
      </div>

      {query.isLoading && <p>Loading…</p>}
      {query.isError && <p className="text-red-600">Could not load notifications.</p>}
      {query.isSuccess && items.length === 0 && <p className="card">Nothing here.</p>}

      <ul className="space-y-2">
        {items.map((n) => {
          const { text, ticketId } = describe(n);
          // read_at is null until the user reads it. This one field is
          // the whole "unread" idea. The database uses it too
          // (partial index ix_notifications_unread).
          const isUnread = n.read_at === null;
          return (
            <li
              key={n.id}
              className={`card flex items-center justify-between ${isUnread ? "font-semibold" : "opacity-70"}`}
            >
              <div>
                {ticketId ? (
                  // Clicking the link opens the ticket AND marks it read.
                  <Link
                    to={`/tickets/${ticketId}`}
                    onClick={() => {
                      if (isUnread) readOne.mutate(n.id);
                    }}
                  >
                    {text}
                  </Link>
                ) : (
                  <span>{text}</span>
                )}
                <div className="text-xs font-normal text-gray-500">
                  {new Date(n.created_at).toLocaleString()}
                </div>
              </div>
              {isUnread && (
                <button className="btn-secondary" onClick={() => readOne.mutate(n.id)}>
                  Mark read
                </button>
              )}
            </li>
          );
        })}
      </ul>

      <div className="flex items-center justify-center gap-3">
        <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <span className="text-sm">
          Page {page} of {totalPages}
        </span>
        <button
          className="btn-secondary"
          disabled={page >= totalPages}
          onClick={() => setPage(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}