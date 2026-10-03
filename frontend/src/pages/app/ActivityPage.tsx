import { useInfiniteQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { ticketFeed } from "../../api/endpoints";
import { PageHeader } from "../../components/AppBits";
import { Avatar, PriorityBadge, StatusBadge } from "../../components/ui/Badges";
import { Button } from "../../components/ui/Button";
import { Alert, EmptyState, Skeleton } from "../../components/ui/Feedback";
import { errorMessage } from "../../lib/errors";
import { formatDay, timeAgo } from "../../lib/format";

// GET /tickets/feed uses a cursor ("give me the tickets after this one")
// instead of page numbers, so new tickets never shift what you have seen.
export function ActivityPage() {
  const feed = useInfiniteQuery({
    queryKey: ["tickets", "feed", "page"],
    queryFn: ({ pageParam }) => ticketFeed(15, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.has_more ? last.next_cursor : null),
  });

  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];
  // A day header above the first ticket of each day.
  const rows = items.map((t, i) => {
    const day = formatDay(t.created_at);
    return { t, day, header: i === 0 || formatDay(items[i - 1].created_at) !== day };
  });

  return (
    <div className="mx-auto max-w-3xl animate-fade-in">
      <PageHeader title="Activity" subtitle="Every ticket you can see, newest first. Updates arrive live." />
      {feed.isError && <Alert>{errorMessage(feed.error)}</Alert>}
      <div className="card p-2 sm:p-4">
        {feed.isPending ? (
          <div className="space-y-3 p-3">
            {[1, 2, 3, 4].map((n) => (
              <Skeleton key={n} className="h-16 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon="activity" title="Nothing here yet" text="New tickets appear here the moment they are raised." />
        ) : (
          <ol className="relative">
            {rows.map(({ t, day, header }) => {
              return (
                <li key={t.id}>
                  {header && <p className="px-3 pt-4 pb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">{day}</p>}
                  <Link to={`/app/tickets/${t.id}`} className="flex gap-4 rounded-xl px-3 py-3.5 transition hover:bg-navy-50/60">
                    <Avatar name={t.requester.full_name} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-600">
                        <span className="font-semibold text-navy-900">{t.requester.full_name}</span> raised{" "}
                        <span className="font-mono text-xs text-slate-500">{t.reference}</span> for {t.team.name}
                      </p>
                      <p className="mt-0.5 truncate font-medium text-navy-900">{t.title}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-3">
                        <StatusBadge status={t.status} />
                        <PriorityBadge priority={t.priority} />
                        <span className="text-xs text-slate-400">{timeAgo(t.created_at)}</span>
                      </div>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ol>
        )}
        {feed.hasNextPage && (
          <div className="p-3 text-center">
            <Button variant="secondary" loading={feed.isFetchingNextPage} onClick={() => void feed.fetchNextPage()}>
              Load more
            </Button>
          </div>
        )}
        {!feed.hasNextPage && items.length > 0 && <p className="py-4 text-center text-xs text-slate-400">You have reached the beginning.</p>}
      </div>
    </div>
  );
}
