import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { exportTicketsCsv, listCategories, listTeams, listTickets, type TicketFilters } from "../../api/endpoints";
import type { SortOrder, TicketPriority, TicketSortField, TicketStatus } from "../../api/types";
import { Perm, useAuth } from "../../auth/auth-context";
import { PageHeader, TicketTable } from "../../components/AppBits";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Alert, EmptyState, Skeleton } from "../../components/ui/Feedback";
import { SelectField } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { Pagination } from "../../components/ui/Pagination";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL } from "../../lib/labels";

const PAGE_SIZE = 20;

const SORTS: { value: TicketSortField; label: string }[] = [
  { value: "created_at", label: "Created" },
  { value: "updated_at", label: "Last updated" },
  { value: "sla_due_at", label: "SLA deadline" },
  { value: "priority", label: "Priority" },
  { value: "status", label: "Status" },
  { value: "relevance", label: "Best match" },
];

// Every filter lives in the URL: refresh, back button and shared links all
// keep the exact same view.
function readFilters(params: URLSearchParams): TicketFilters {
  const bool = (key: string) => (params.get(key) === "true" ? true : undefined);
  return {
    status: (params.get("status") as TicketStatus) || undefined,
    priority: (params.get("priority") as TicketPriority) || undefined,
    category_id: params.get("category_id") || undefined,
    team_id: params.get("team_id") || undefined,
    assignee_id: params.get("assignee_id") || undefined,
    requester_id: params.get("requester_id") || undefined,
    unassigned: bool("unassigned"),
    sla_breached: bool("sla_breached"),
    created_after: params.get("created_after") || undefined,
    created_before: params.get("created_before") || undefined,
    q: params.get("q") || undefined,
    sort: (params.get("sort") as TicketSortField) || undefined,
    order: (params.get("order") as SortOrder) || undefined,
  };
}

export function TicketsPage() {
  const { user, can } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);
  const [exporting, setExporting] = useState(false);
  const filters = readFilters(params);
  const page = Number(params.get("page") ?? "1") || 1;
  const staff = can(Perm.WORK);
  const me = user!.id;

  const tickets = useQuery({
    queryKey: ["tickets", "list", filters, page],
    queryFn: () => listTickets({ ...filters, page, size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: 300_000 });
  const teams = useQuery({ queryKey: ["teams"], queryFn: listTeams, staleTime: 300_000 });

  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    // "Best match" needs a search text; drop it when the text is cleared.
    if (!next.get("q") && next.get("sort") === "relevance") next.delete("sort");
    setParams(next);
  }

  const views = [
    { label: "All", active: !filters.assignee_id && !filters.requester_id && !filters.unassigned && !filters.sla_breached, set: { assignee_id: undefined, requester_id: undefined, unassigned: undefined, sla_breached: undefined } },
    ...(staff
      ? [
          { label: "Assigned to me", active: filters.assignee_id === me, set: { assignee_id: me, requester_id: undefined, unassigned: undefined, sla_breached: undefined } },
          { label: "Unassigned", active: filters.unassigned === true, set: { unassigned: "true", assignee_id: undefined, requester_id: undefined, sla_breached: undefined } },
        ]
      : []),
    { label: "Raised by me", active: filters.requester_id === me, set: { requester_id: me, assignee_id: undefined, unassigned: undefined, sla_breached: undefined } },
    { label: "Breached", active: filters.sla_breached === true, set: { sla_breached: "true", assignee_id: undefined, requester_id: undefined, unassigned: undefined } },
  ];

  const activeFilterCount = [filters.status, filters.priority, filters.category_id, filters.team_id, filters.created_after, filters.created_before].filter(Boolean).length;

  async function onExport() {
    setExporting(true);
    try {
      await exportTicketsCsv(filters);
      toast("Export downloaded.");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Tickets"
        subtitle={tickets.data ? (tickets.data.total === 1 ? "1 ticket matches this view" : `${tickets.data.total} tickets match this view`) : "Loading"}
        actions={
          <>
            <Button variant="secondary" icon="download" loading={exporting} onClick={onExport}>
              Export CSV
            </Button>
            <ButtonLink to="/app/tickets/new" icon="plus">
              New ticket
            </ButtonLink>
          </>
        }
      />

      <div className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 lg:flex-row lg:items-center">
          <div className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1">
            {views.map((v) => (
              <button
                key={v.label}
                type="button"
                onClick={() => update(v.set)}
                className={`rounded-md px-3 py-1.5 text-sm transition ${v.active ? "bg-white font-medium text-navy-900 shadow-sm" : "text-slate-600 hover:text-navy-900"}`}
              >
                {v.label}
              </button>
            ))}
          </div>
          <div className="flex flex-1 flex-wrap items-center gap-2 lg:justify-end">
            <SearchBox key={filters.q ?? ""} initial={filters.q ?? ""} onSearch={(q) => update({ q: q || undefined, sort: q ? "relevance" : filters.sort })} />
            <Button variant={showFilters || activeFilterCount ? "primary" : "secondary"} icon="filter" onClick={() => setShowFilters((s) => !s)}>
              Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}
            </Button>
          </div>
        </div>

        {showFilters && (
          <div className="grid animate-fade-in gap-4 border-b border-slate-100 bg-slate-50/60 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <SelectField label="Status" value={filters.status ?? ""} onChange={(e) => update({ status: e.target.value || undefined })}>
              <option value="">Any status</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{STATUS_LABEL[s]}</option>
              ))}
            </SelectField>
            <SelectField label="Priority" value={filters.priority ?? ""} onChange={(e) => update({ priority: e.target.value || undefined })}>
              <option value="">Any priority</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
              ))}
            </SelectField>
            <SelectField label="Team" value={filters.team_id ?? ""} onChange={(e) => update({ team_id: e.target.value || undefined })}>
              <option value="">Any team</option>
              {teams.data?.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </SelectField>
            <SelectField label="Category" value={filters.category_id ?? ""} onChange={(e) => update({ category_id: e.target.value || undefined })}>
              <option value="">Any category</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </SelectField>
            <div>
              <label className="label" htmlFor="from">Created from</label>
              <input id="from" type="date" className="field" value={filters.created_after?.slice(0, 10) ?? ""} onChange={(e) => update({ created_after: e.target.value ? `${e.target.value}T00:00:00Z` : undefined })} />
            </div>
            <div>
              <label className="label" htmlFor="to">Created until</label>
              <input id="to" type="date" className="field" value={filters.created_before?.slice(0, 10) ?? ""} onChange={(e) => update({ created_before: e.target.value ? `${e.target.value}T23:59:59Z` : undefined })} />
            </div>
            <SelectField label="Sort by" value={filters.sort ?? "created_at"} onChange={(e) => update({ sort: e.target.value })}>
              {SORTS.filter((s) => s.value !== "relevance" || filters.q).map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </SelectField>
            <SelectField label="Order" value={filters.order ?? "desc"} onChange={(e) => update({ order: e.target.value })} disabled={filters.sort === "relevance"}>
              <option value="desc">Newest or highest first</option>
              <option value="asc">Oldest or lowest first</option>
            </SelectField>
            <div className="sm:col-span-2 lg:col-span-4">
              <Button variant="ghost" size="sm" icon="x" onClick={() => setParams(new URLSearchParams())}>
                Clear all filters
              </Button>
            </div>
          </div>
        )}

        {filters.q && (
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-leaf-50/60 px-4 py-2.5 text-sm text-slate-600">
            <Icon name="search" className="size-4 text-leaf-600" />
            Results for <b className="text-navy-900">"{filters.q}"</b>
            {filters.sort === "relevance" && <span className="chip bg-white text-leaf-700">sorted by best match</span>}
            <button type="button" onClick={() => update({ q: undefined })} className="ml-auto text-xs font-medium text-navy-700 hover:text-navy-900">
              Clear search
            </button>
          </div>
        )}

        {tickets.isError ? (
          <div className="p-5">
            <Alert>{errorMessage(tickets.error)}</Alert>
          </div>
        ) : tickets.isPending ? (
          <div className="space-y-3 p-5">
            {[1, 2, 3, 4, 5].map((n) => (
              <Skeleton key={n} className="h-12 w-full" />
            ))}
          </div>
        ) : tickets.data.items.length === 0 ? (
          <EmptyState
            icon="search"
            title="No tickets match this view"
            text={filters.q ? "Try other words. Search matches whole words: printers finds printer, print does not." : "Change the filters, or raise a new ticket."}
            action={<Button variant="secondary" onClick={() => setParams(new URLSearchParams())}>Reset view</Button>}
          />
        ) : (
          <div className={tickets.isPlaceholderData ? "opacity-60 transition" : "transition"}>
            <TicketTable tickets={tickets.data.items} />
            <Pagination page={page} pages={tickets.data.pages} total={tickets.data.total} size={PAGE_SIZE} onChange={(p) => update({ page: String(p) })} />
          </div>
        )}
      </div>

      <p className="mt-4 text-center text-xs text-slate-400">
        Search tips: use quotes for a phrase, <b>or</b> for either word, and a minus sign to exclude a word.
      </p>
    </div>
  );
}

function SearchBox({ initial, onSearch }: { initial: string; onSearch: (q: string) => void }) {
  const [text, setText] = useState(initial);
  function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    // The API needs at least 2 characters (TicketFilters.q min_length=2).
    if (q.length === 1) return;
    onSearch(q);
  }
  return (
    <form onSubmit={submit} className="relative w-full sm:w-72">
      <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder='Search, e.g. "vpn error" -home' className="field pl-9" aria-label="Search tickets" />
    </form>
  );
}
