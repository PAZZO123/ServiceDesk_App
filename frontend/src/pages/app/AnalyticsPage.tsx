import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { teamSla } from "../../api/endpoints";
import { PageHeader, SectionCard, StatCard } from "../../components/AppBits";
import { BarList } from "../../components/Charts";
import { Alert, EmptyState, Skeleton } from "../../components/ui/Feedback";
import { Icon } from "../../components/ui/Icon";
import { formatHours } from "../../lib/format";

const PERIODS = [7, 30, 90, 365];

// GET /analytics/teams: one SQL query with two CTEs, FILTER counts, a
// median and two window functions (share of total, rank) on the server.
export function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const report = useQuery({ queryKey: ["analytics", "teams", days], queryFn: () => teamSla(days), placeholderData: keepPreviousData });
  const rows = report.data ?? [];

  const created = rows.reduce((s, r) => s + r.created, 0);
  const resolved = rows.reduce((s, r) => s + r.resolved, 0);
  const breached = rows.reduce((s, r) => s + r.breached, 0);
  // Weighted overall SLA rate: in-time resolutions over all resolutions.
  const inTime = rows.reduce((s, r) => s + (r.sla_met_pct ?? 0) * r.resolved, 0);
  const overall = resolved ? Math.round((inTime / resolved) * 10) / 10 : null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Analytics"
        subtitle="How each team performs against its SLAs."
        actions={
          <div className="flex rounded-lg bg-white p-1 shadow-card">
            {PERIODS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={`rounded-md px-3 py-1.5 text-sm transition ${d === days ? "bg-navy-900 font-medium text-white" : "text-slate-600 hover:text-navy-900"}`}
              >
                {d === 365 ? "1 year" : `${d} days`}
              </button>
            ))}
          </div>
        }
      />
      {report.isError && <Alert>The report could not be loaded. Only users who can see every ticket may open it.</Alert>}

      <div className={`grid gap-4 sm:grid-cols-2 xl:grid-cols-4 ${report.isPlaceholderData ? "opacity-60" : ""}`}>
        <StatCard label="Tickets raised" value={report.isPending ? <Skeleton className="h-8 w-14" /> : created} icon="ticket" hint={`Last ${days} days`} />
        <StatCard label="Resolved" value={report.isPending ? <Skeleton className="h-8 w-14" /> : resolved} icon="checkCircle" tone="leaf" />
        <StatCard label="SLA met overall" value={overall === null ? "No data" : `${overall}%`} icon="clock" tone={overall !== null && overall < 90 ? "amber" : "leaf"} hint="Resolved before the deadline" />
        <StatCard label="Currently breached" value={breached} icon="alert" tone={breached ? "red" : "leaf"} />
      </div>

      {!report.isPending && rows.length === 0 ? (
        <div className="card mt-6">
          <EmptyState icon="chart" title="No teams yet" />
        </div>
      ) : (
        <>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <SectionCard title="SLA met per team">
              <div className="p-5">
                {report.isPending ? <Skeleton className="h-40 w-full" /> : <BarList max={100} unit="%" good={(v) => v >= 90} bars={rows.map((r) => ({ label: r.name, value: r.sla_met_pct, note: `${r.resolved} resolved` }))} />}
              </div>
            </SectionCard>
            <SectionCard title="Share of all tickets">
              <div className="p-5">
                {report.isPending ? <Skeleton className="h-40 w-full" /> : <BarList max={100} unit="%" bars={rows.map((r) => ({ label: r.name, value: r.share_pct ?? 0, note: `${r.created} raised` }))} />}
              </div>
            </SectionCard>
          </div>

          <SectionCard title="Ranking" className="mt-6">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px]">
                <thead className="bg-slate-50/80">
                  <tr>
                    <th className="table-head w-16">Rank</th>
                    <th className="table-head">Team</th>
                    <th className="table-head text-right">Raised</th>
                    <th className="table-head text-right">Resolved</th>
                    <th className="table-head text-right">Breached</th>
                    <th className="table-head text-right">Median time</th>
                    <th className="table-head text-right">SLA met</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((r) => (
                    <tr key={r.team_id} className="hover:bg-navy-50/40">
                      <td className="table-cell">
                        <span className={`grid size-8 place-items-center rounded-full text-sm font-semibold ${r.sla_rank === 1 && r.sla_met_pct !== null ? "bg-leaf-500 text-navy-950" : "bg-navy-50 text-navy-700"}`}>{r.sla_rank}</span>
                      </td>
                      <td className="table-cell font-medium text-navy-900">{r.name}</td>
                      <td className="table-cell text-right">{r.created}</td>
                      <td className="table-cell text-right">{r.resolved}</td>
                      <td className={`table-cell text-right ${r.breached ? "font-semibold text-red-600" : ""}`}>{r.breached}</td>
                      <td className="table-cell text-right">{formatHours(r.median_hours)}</td>
                      <td className="table-cell text-right font-semibold text-navy-900">{r.sla_met_pct === null ? "No data" : `${r.sla_met_pct}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="flex items-center gap-2 border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
              <Icon name="info" className="size-3.5" />
              Median time is used instead of the average, so one ticket stuck for weeks does not hide that most are solved quickly.
            </p>
          </SectionCard>
        </>
      )}
    </div>
  );
}
