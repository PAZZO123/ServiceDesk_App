import type { ReactNode } from "react";
import { Link } from "react-router";
import type { TicketListItem } from "../api/types";
import { timeAgo } from "../lib/format";
import { Avatar, PriorityBadge, SlaBadge, StatusBadge, TagChip } from "./ui/Badges";
import { Icon, type IconName } from "./ui/Icon";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      {/* React 19 moves a <title> rendered anywhere into <head>. */}
      <title>{`${title} | ServiceDesk`}</title>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-navy-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

const STAT_TONES = {
  navy: "bg-navy-900 text-leaf-400",
  leaf: "bg-leaf-100 text-leaf-700",
  red: "bg-red-50 text-red-600",
  amber: "bg-amber-50 text-amber-600",
  sky: "bg-sky-50 text-sky-600",
} as const;

export function StatCard({
  label,
  value,
  icon,
  tone = "navy",
  hint,
  to,
}: {
  label: string;
  value: ReactNode;
  icon: IconName;
  tone?: keyof typeof STAT_TONES;
  hint?: string;
  to?: string;
}) {
  const body = (
    <div className="card flex h-full items-start justify-between gap-4 p-5 transition hover:shadow-float">
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <div className="mt-2 text-3xl font-semibold tracking-tight text-navy-900">{value}</div>
        {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      </div>
      <span className={`grid size-11 shrink-0 place-items-center rounded-xl ${STAT_TONES[tone]}`}>
        <Icon name={icon} />
      </span>
    </div>
  );
  return to ? (
    <Link to={to} className="block rounded-xl">
      {body}
    </Link>
  ) : (
    body
  );
}

export function SectionCard({ title, action, children, className = "" }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card overflow-hidden ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold text-navy-900">{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

const DONE = new Set(["resolved", "closed"]);

// The ticket table used by the tickets page and the dashboard.
export function TicketTable({ tickets, compact = false }: { tickets: TicketListItem[]; compact?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px]">
        <thead className="bg-slate-50/80">
          <tr>
            <th className="table-head">Ticket</th>
            <th className="table-head">Status</th>
            <th className="table-head">Priority</th>
            {!compact && <th className="table-head">Team</th>}
            <th className="table-head">Assignee</th>
            <th className="table-head">SLA</th>
            {!compact && <th className="table-head text-right">Updated</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((t) => (
            <tr key={t.id} className="group transition hover:bg-navy-50/50">
              <td className="table-cell max-w-[22rem]">
                <Link to={`/app/tickets/${t.id}`} className="block">
                  <span className="font-mono text-xs text-slate-400">{t.reference}</span>
                  <span className="block truncate font-medium text-navy-900 group-hover:text-navy-700">{t.title}</span>
                  {!compact && (t.tags?.length ?? 0) > 0 && (
                    <span className="mt-1.5 flex flex-wrap gap-1">
                      {t.tags!.map((tag) => (
                        <TagChip key={tag.id} name={tag.name} color={tag.color} />
                      ))}
                    </span>
                  )}
                </Link>
              </td>
              <td className="table-cell">
                <StatusBadge status={t.status} />
              </td>
              <td className="table-cell">
                <PriorityBadge priority={t.priority} />
              </td>
              {!compact && (
                <td className="table-cell">
                  <span className="block text-sm text-slate-700">{t.team.name}</span>
                  <span className="block text-xs text-slate-400">{t.category.name}</span>
                </td>
              )}
              <td className="table-cell">
                {t.assignee ? (
                  <span className="flex items-center gap-2">
                    <Avatar name={t.assignee.full_name} size="sm" />
                    <span className="truncate">{t.assignee.full_name}</span>
                  </span>
                ) : (
                  <span className="text-slate-400">Unassigned</span>
                )}
              </td>
              <td className="table-cell">
                <SlaBadge dueAt={t.sla_due_at} breached={t.sla_breached} done={DONE.has(t.status)} />
              </td>
              {!compact && <td className="table-cell text-right text-xs whitespace-nowrap text-slate-500">{timeAgo(t.updated_at)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
