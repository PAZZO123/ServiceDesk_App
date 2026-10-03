import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { listNotifications, markAllNotificationsRead, markNotificationRead } from "../../api/endpoints";
import type { NotificationItem, NotificationType } from "../../api/types";
import { PageHeader } from "../../components/AppBits";
import { Button } from "../../components/ui/Button";
import { Alert, EmptyState, Skeleton } from "../../components/ui/Feedback";
import { Icon, type IconName } from "../../components/ui/Icon";
import { Pagination } from "../../components/ui/Pagination";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatDate, timeAgo } from "../../lib/format";
import { NOTIFICATION_LABEL } from "../../lib/labels";

const SIZE = 15;

const ICONS: Record<NotificationType, { icon: IconName; tone: string }> = {
  ticket_assigned: { icon: "ticket", tone: "bg-navy-900 text-leaf-400" },
  ticket_status_changed: { icon: "refresh", tone: "bg-sky-50 text-sky-600" },
  comment_added: { icon: "message", tone: "bg-leaf-100 text-leaf-700" },
  sla_breached: { icon: "alert", tone: "bg-red-50 text-red-600" },
  ticket_mentioned: { icon: "user", tone: "bg-indigo-50 text-indigo-600" },
};

// The payload differs per type (see the services that create them); read
// the keys defensively and fall back to the type's label.
function describe(n: NotificationItem): { title: string; text: string; ticketId: string | null } {
  const p = n.payload as Record<string, unknown>;
  const str = (key: string) => (typeof p[key] === "string" ? (p[key] as string) : "");
  const ref = str("reference");
  const ticketId = str("ticket_id") || null;
  switch (n.type) {
    case "comment_added":
      return {
        title: `${str("author") || "Someone"} ${p.internal ? "added an internal note" : "replied"}${ref ? ` on ${ref}` : ""}`,
        text: str("preview"),
        ticketId,
      };
    case "ticket_assigned":
      return {
        title: str("assigned_by") ? `${str("assigned_by")} assigned you ${ref}` : `New ticket ${ref} for your team`,
        text: str("title"),
        ticketId,
      };
    case "sla_breached":
      return { title: `${ref} passed its SLA deadline`, text: str("title"), ticketId };
    default:
      return { title: `${NOTIFICATION_LABEL[n.type]}${ref ? `: ${ref}` : ""}`, text: str("title") || str("message"), ticketId };
  }
}

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();
  const toast = useToast();

  const list = useQuery({
    queryKey: ["notifications", unreadOnly, page],
    queryFn: () => listNotifications(page, SIZE, unreadOnly),
    placeholderData: keepPreviousData,
  });

  // No need to refresh the badge: the SSE stream pushes the new count.
  const readOne = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const readAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast("All caught up.");
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });

  return (
    <div className="mx-auto max-w-3xl animate-fade-in">
      <PageHeader
        title="Notifications"
        subtitle="Assignments, replies and SLA alerts. The badge updates live."
        actions={
          <Button variant="secondary" icon="checkCircle" loading={readAll.isPending} onClick={() => readAll.mutate()}>
            Mark all as read
          </Button>
        }
      />
      <div className="card overflow-hidden">
        <div className="flex gap-1 border-b border-slate-100 p-3">
          {[
            [false, "All"],
            [true, "Unread"],
          ].map(([value, label]) => (
            <button
              key={String(label)}
              type="button"
              onClick={() => {
                setUnreadOnly(value as boolean);
                setPage(1);
              }}
              className={`rounded-lg px-3.5 py-1.5 text-sm transition ${unreadOnly === value ? "bg-navy-900 font-medium text-white" : "text-slate-600 hover:bg-slate-100"}`}
            >
              {label as string}
            </button>
          ))}
        </div>
        {list.isError && (
          <div className="p-4">
            <Alert>{errorMessage(list.error)}</Alert>
          </div>
        )}
        {list.isPending ? (
          <div className="space-y-3 p-4">
            {[1, 2, 3].map((n) => (
              <Skeleton key={n} className="h-14 w-full" />
            ))}
          </div>
        ) : list.data && list.data.items.length === 0 ? (
          <EmptyState icon="bell" title={unreadOnly ? "No unread notifications" : "No notifications yet"} text="You will be told here when something needs you." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {list.data?.items.map((n) => {
              const { title, text, ticketId } = describe(n);
              const unread = n.read_at === null;
              const look = ICONS[n.type];
              const content = (
                <>
                  <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${look.tone}`}>
                    <Icon name={look.icon} className="size-4.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className={`block text-sm ${unread ? "font-semibold text-navy-900" : "text-slate-700"}`}>{title}</span>
                    {text && <span className="mt-0.5 block truncate text-sm text-slate-500">{text}</span>}
                    <span className="mt-1 block text-xs text-slate-400" title={formatDate(n.created_at)}>
                      {timeAgo(n.created_at)}
                    </span>
                  </span>
                  {unread && <span className="mt-1.5 size-2.5 shrink-0 rounded-full bg-leaf-500" aria-label="Unread" />}
                </>
              );
              const className = `flex gap-4 px-5 py-4 transition ${unread ? "bg-leaf-50/40 hover:bg-leaf-50" : "hover:bg-slate-50"}`;
              return (
                <li key={n.id}>
                  {ticketId ? (
                    <Link to={`/app/tickets/${ticketId}`} className={className} onClick={() => unread && readOne.mutate(n.id)}>
                      {content}
                    </Link>
                  ) : (
                    <button type="button" className={`${className} w-full text-left`} onClick={() => unread && readOne.mutate(n.id)}>
                      {content}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {list.data && <Pagination page={page} pages={list.data.pages} total={list.data.total} size={SIZE} onChange={setPage} />}
      </div>
    </div>
  );
}
