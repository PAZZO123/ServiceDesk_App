import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { listTickets, teamSla, ticketFeed, type TicketFilters } from "../../api/endpoints";
import { Perm, useAuth } from "../../auth/auth-context";
import { PageHeader, SectionCard, StatCard, TicketTable } from "../../components/AppBits";
import { BarList, Donut } from "../../components/Charts";
import { StatusBadge } from "../../components/ui/Badges";
import { ButtonLink } from "../../components/ui/Button";
import { EmptyState, Skeleton } from "../../components/ui/Feedback";
import { Icon } from "../../components/ui/Icon";
import { timeAgo } from "../../lib/format";
import { STATUS_LABEL, STATUSES } from "../../lib/labels";
import { useUnreadCount } from "../../realtime/useUnreadCount";

const STATUS_COLORS = {
  open: "#0ea5e9",
  in_progress: "#6366f1",
  waiting: "#f59e0b",
  resolved: "#89c550",
  closed: "#94a3b8",
} as const;

// "How many tickets match?" = page size 1 and read `total`.
function countQuery(key: string, filters: TicketFilters) {
  return {
    queryKey: ["tickets", "count", key, filters],
    queryFn: () => listTickets({ ...filters, size: 1 }).then((page) => page.total),
  };
}

function greeting(): string {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export function DashboardPage() {
  const { user, can } = useAuth();
  const unread = useUnreadCount();
  const staff = can(Perm.WORK);
  const manager = can(Perm.VIEW_ALL);
  const me = user!.id;

  // Visible tickets per status (the API already limits what each user sees).
  const statusCounts = useQueries({
    queries: STATUSES.map((status) => countQuery(status, { status })),
  });

  const kpis = useQueries({
    queries: [
      countQuery("breached", { sla_breached: true }),
      countQuery("mine-open", staff ? { assignee_id: me, status: "in_progress" } : { requester_id: me, status: "open" }),
      countQuery("unclaimed", { unassigned: true, status: "open" }),
    ],
  });

  const upcoming = useQuery({
    queryKey: ["tickets", "dashboard", staff ? "deadlines" : "mine"],
    queryFn: () =>
      staff
        ? listTickets({ status: "open", sort: "sla_due_at", order: "asc", size: 6 })
        : listTickets({ requester_id: me, sort: "updated_at", order: "desc", size: 6 }),
  });

  const feed = useQuery({ queryKey: ["tickets", "feed", "dashboard"], queryFn: () => ticketFeed(6) });

  const analytics = useQuery({
    queryKey: ["analytics", "teams", 30],
    queryFn: () => teamSla(30),
    enabled: manager,
  });

  const counts = statusCounts.map((q) => q.data ?? 0);
  const total = counts.reduce((a, b) => a + b, 0);
  const active = counts[0] + counts[1] + counts[2];
  const loadingCounts = statusCounts.some((q) => q.isPending);
  const [breached, mine, unclaimed] = kpis.map((q) => q.data);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={`${greeting()}, ${user!.full_name.split(" ")[0]}`}
        subtitle={staff ? "Here is what needs your attention today." : "Here is where your requests stand."}
        actions={
          <>
            <ButtonLink to="/app/tickets" variant="secondary" icon="ticket">
              All tickets
            </ButtonLink>
            <ButtonLink to="/app/tickets/new" icon="plus">
              New ticket
            </ButtonLink>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active tickets" value={loadingCounts ? <Skeleton className="h-8 w-14" /> : active} icon="ticket" hint="Open, in progress or waiting" to="/app/tickets" />
        {staff ? (
          <StatCard label="In progress with you" value={mine ?? "…"} icon="user" tone="sky" to={`/app/tickets?assignee_id=${me}&status=in_progress`} />
        ) : (
          <StatCard label="Your open requests" value={mine ?? "…"} icon="user" tone="sky" to={`/app/tickets?requester_id=${me}&status=open`} />
        )}
        {staff ? (
          <StatCard label="Waiting for an owner" value={unclaimed ?? "…"} icon="inbox" tone="amber" hint="Open and unassigned" to="/app/tickets?unassigned=true&status=open" />
        ) : (
          <StatCard label="Unread notifications" value={unread ?? "…"} icon="bell" tone="amber" to="/app/notifications" />
        )}
        <StatCard label="SLA breached" value={breached ?? "…"} icon="alert" tone={breached ? "red" : "leaf"} hint={breached ? "Past their deadline" : "Nothing late, well done"} to="/app/tickets?sla_breached=true" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <SectionCard title="Tickets by status" className="xl:col-span-1">
          <div className="p-5">
            {loadingCounts ? (
              <Skeleton className="h-40 w-full" />
            ) : total === 0 ? (
              <EmptyState icon="ticket" title="No tickets yet" text="Raised tickets will show up here." />
            ) : (
              <Donut
                centerLabel="tickets"
                centerValue={total}
                slices={STATUSES.map((s, i) => ({ label: STATUS_LABEL[s], value: counts[i], color: STATUS_COLORS[s] }))}
              />
            )}
          </div>
        </SectionCard>

        <SectionCard
          title={staff ? "Next deadlines" : "Your recent tickets"}
          className="xl:col-span-2"
          action={
            <Link to={staff ? "/app/tickets?status=open&sort=sla_due_at&order=asc" : `/app/tickets?requester_id=${me}`} className="text-sm font-medium text-navy-700 hover:text-navy-900">
              View all
            </Link>
          }
        >
          {upcoming.isPending ? (
            <div className="space-y-3 p-5">
              {[1, 2, 3].map((n) => (
                <Skeleton key={n} className="h-10 w-full" />
              ))}
            </div>
          ) : upcoming.data && upcoming.data.items.length > 0 ? (
            <TicketTable tickets={upcoming.data.items} compact />
          ) : (
            <EmptyState
              icon="checkCircle"
              title={staff ? "The open queue is empty" : "No tickets yet"}
              text={staff ? "Nothing open in your teams right now." : "Raise a ticket and follow it here."}
              action={!staff && <ButtonLink to="/app/tickets/new" icon="plus">Raise a ticket</ButtonLink>}
            />
          )}
        </SectionCard>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <SectionCard
          title="Recent activity"
          className={manager ? "xl:col-span-1" : "xl:col-span-3"}
          action={
            <Link to="/app/activity" className="text-sm font-medium text-navy-700 hover:text-navy-900">
              Open feed
            </Link>
          }
        >
          <ul className="divide-y divide-slate-100">
            {feed.isPending &&
              [1, 2, 3].map((n) => (
                <li key={n} className="p-4">
                  <Skeleton className="h-8 w-full" />
                </li>
              ))}
            {feed.data?.items.map((t) => (
              <li key={t.id}>
                <Link to={`/app/tickets/${t.id}`} className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-navy-50/50">
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-navy-50 text-navy-700">
                    <Icon name="ticket" className="size-4.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-navy-900">{t.title}</span>
                    <span className="block text-xs text-slate-400">
                      {t.reference} · raised {timeAgo(t.created_at)} by {t.requester.full_name}
                    </span>
                  </span>
                  <StatusBadge status={t.status} />
                </Link>
              </li>
            ))}
            {feed.data?.items.length === 0 && <EmptyState icon="activity" title="No activity yet" />}
          </ul>
        </SectionCard>

        {manager && (
          <SectionCard
            title="SLA met by team, last 30 days"
            className="xl:col-span-2"
            action={
              <Link to="/app/analytics" className="text-sm font-medium text-navy-700 hover:text-navy-900">
                Full analytics
              </Link>
            }
          >
            <div className="p-5">
              {analytics.isPending ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <BarList
                  max={100}
                  unit="%"
                  good={(v) => v >= 90}
                  bars={(analytics.data ?? []).map((row) => ({
                    label: row.name,
                    value: row.sla_met_pct,
                    note: `${row.resolved} resolved`,
                  }))}
                />
              )}
            </div>
          </SectionCard>
        )}
      </div>
    </div>
  );
}
