import type { TicketPriority, TicketStatus } from "../../api/types";
import { initials } from "../../lib/format";
import { PRIORITY_LABEL, STATUS_LABEL } from "../../lib/labels";
import { useNow } from "../../lib/use-now";
import { Icon } from "./Icon";

const STATUS_STYLE: Record<TicketStatus, string> = {
  open: "bg-sky-50 text-sky-700 ring-sky-600/20",
  in_progress: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  waiting: "bg-amber-50 text-amber-700 ring-amber-600/20",
  resolved: "bg-leaf-50 text-leaf-700 ring-leaf-600/25",
  closed: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

const STATUS_DOT: Record<TicketStatus, string> = {
  open: "bg-sky-500",
  in_progress: "bg-indigo-500",
  waiting: "bg-amber-500",
  resolved: "bg-leaf-500",
  closed: "bg-slate-400",
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={`chip ring-1 ring-inset ${STATUS_STYLE[status]}`}>
      <span className={`size-1.5 rounded-full ${STATUS_DOT[status]}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

const PRIORITY_STYLE: Record<TicketPriority, string> = {
  low: "text-slate-500",
  medium: "text-sky-600",
  high: "text-orange-600",
  urgent: "text-red-600",
};

const PRIORITY_BARS: Record<TicketPriority, number> = { low: 1, medium: 2, high: 3, urgent: 4 };

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const bars = PRIORITY_BARS[priority];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${PRIORITY_STYLE[priority]}`}>
      <span className="flex items-end gap-0.5" aria-hidden>
        {[1, 2, 3, 4].map((n) => (
          <span key={n} className={`w-0.75 rounded-sm ${n <= bars ? "bg-current" : "bg-slate-200"}`} style={{ height: 3 + n * 2.5 }} />
        ))}
      </span>
      {PRIORITY_LABEL[priority]}
    </span>
  );
}

// Shows how long until the SLA deadline, or that it has passed.
export function SlaBadge({ dueAt, breached, done }: { dueAt: string; breached: boolean; done: boolean }) {
  const now = useNow();
  if (done) return <span className="text-xs text-slate-400">Done</span>;
  const msLeft = new Date(dueAt).getTime() - now;
  if (breached || msLeft < 0) {
    return (
      <span className="chip bg-red-50 text-red-700 ring-1 ring-red-600/20 ring-inset">
        <Icon name="alert" className="size-3.5" />
        Breached
      </span>
    );
  }
  const hours = msLeft / 3_600_000;
  const soon = hours < 2;
  const text = hours < 1 ? `${Math.max(1, Math.round(hours * 60))} min left` : hours < 48 ? `${Math.round(hours)} h left` : `${Math.round(hours / 24)} days left`;
  return (
    <span className={`chip ring-1 ring-inset ${soon ? "bg-amber-50 text-amber-700 ring-amber-600/20" : "bg-slate-50 text-slate-600 ring-slate-500/15"}`}>
      <Icon name="clock" className="size-3.5" />
      {text}
    </span>
  );
}

const AVATAR_COLORS = ["bg-navy-700", "bg-leaf-600", "bg-sky-600", "bg-indigo-600", "bg-amber-600", "bg-rose-600"];

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const color = AVATAR_COLORS[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % AVATAR_COLORS.length];
  const dims = size === "sm" ? "size-6 text-[10px]" : size === "lg" ? "size-11 text-base" : "size-8 text-xs";
  return (
    <span className={`inline-grid shrink-0 place-items-center rounded-full font-semibold text-white ${color} ${dims}`} title={name}>
      {initials(name)}
    </span>
  );
}

export function TagChip({ name, color }: { name: string; color: string }) {
  return (
    <span className="chip bg-white text-slate-700 ring-1 ring-slate-200 ring-inset">
      <span className="size-2 rounded-full" style={{ backgroundColor: color }} />
      {name}
    </span>
  );
}
