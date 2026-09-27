import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router";
import { listTickets } from "../api/endpoints";
import type { TicketStatus } from "../api/types";
import { PriorityBadge, StatusBadge } from "../components/badges";
import { formatDate } from "../lib/format";
const PAGE_SIZE = 10;
const STATUSES: TicketStatus[] = ["open", "in_progress", "waiting", "resolved", "closed"];


function SearchBox({ initial, onSearch }: { initial: string; onSearch: (q: string) => void }) {
  const [text, setText] = useState(initial);
  const [hint, setHint] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = text.trim();
    if (value.length === 1) {
      setHint("Type at least 2 characters.");
      return;
    }
    setHint(null);
    onSearch(value);
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        className="input w-64"
        placeholder="Search title or description"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button className="btn-secondary" type="submit">
        Search
      </button>
      {hint && <span className="text-xs text-red-700">{hint}</span>}
    </form>
  );
}

export default function TicketListPage() {
  const location = useLocation();
  const created = (location.state as { created?: string } | null)?.created;
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const status = STATUSES.find((s) => s === params.get("status"));
  const q = params.get("q") ?? "";

  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  }

  const tickets = useQuery({
    queryKey: ["tickets", { page, status, q }],
    queryFn: () => listTickets({ page, size: PAGE_SIZE, status, q: q || undefined }),
    // Keep the old page on screen while the next one loads - no flicker.
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Tickets</h1>
        <Link to="/tickets/new" className="btn">
          New ticket
        </Link>
      </div>

      {created && (
        <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
          {created} was created.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <select
          className="input w-44"
          value={status ?? ""}
          onChange={(e) => update({ status: e.target.value || undefined, page: undefined })}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>

    
    
        <SearchBox key={q} initial={q} onSearch={(value) => update({ q: value || undefined, page: undefined })} />

        {tickets.isFetching && <span className="text-xs text-slate-500">Updating…</span>}
      </div>

      {tickets.isPending && <p className="text-slate-500">Loading tickets…</p>}
      {tickets.isError && <p className="text-red-700">{tickets.error.message}</p>}

      {tickets.data && (
        <>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Reference</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Priority</th>
                  <th className="px-3 py-2">Team</th>
                  <th className="px-3 py-2">Requester</th>
                  <th className="px-3 py-2">Assignee</th>
                  <th className="px-3 py-2">SLA due</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tickets.data.items.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 font-mono">
                      <Link to={`/tickets/${t.id}`} className="text-blue-700 hover:underline">
                        {t.reference}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{t.title}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="px-3 py-2">
                      <PriorityBadge priority={t.priority} />
                    </td>
                    <td className="px-3 py-2">{t.team.name}</td>
                    <td className="px-3 py-2">{t.requester.full_name}</td>
                    <td className="px-3 py-2">
                      {t.assignee?.full_name ?? <span className="text-slate-400">unassigned</span>}
                    </td>
                    <td className={`px-3 py-2 ${t.sla_breached ? "font-semibold text-red-700" : ""}`}>
                      {formatDate(t.sla_due_at)}
                    </td>
                  </tr>
                ))}
                {tickets.data.items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-3 py-6 text-center text-slate-500">
                      No tickets match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              {tickets.data.total} ticket{tickets.data.total === 1 ? "" : "s"}
            </span>
            <div className="flex items-center gap-2">
              <button
                className="btn-secondary"
                disabled={page <= 1}
                onClick={() => update({ page: String(page - 1) })}
              >
                Previous
              </button>
              <span>
                Page {page} of {Math.max(1, tickets.data.pages)}
              </span>
              <button
                className="btn-secondary"
                disabled={page >= tickets.data.pages}
                onClick={() => update({ page: String(page + 1) })}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}