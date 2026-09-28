import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "../api/client";
import {
    addComment,
    changeStatus,
    claimTicket,
    downloadAttachment,
    getTicket,
    listAttachments,
    listComments,
    uploadAttachment,
} from "../api/endpoints";
import type { TicketRead, TicketStatus } from "../api/types";
import { Perm, useAuth } from "../auth/auth-context";
import { PriorityBadge, StatusBadge } from "../components/badges";
import { formatDate } from "../lib/format";

const NEXT_STATUSES: Record<TicketStatus, TicketStatus[]> = {
  open: ["in_progress", "waiting", "resolved", "closed"],
  in_progress: ["open", "waiting", "resolved"],
  waiting: ["open", "in_progress", "resolved"],
  resolved: ["closed", "in_progress"],
  closed: [],
};

function useAbilities(ticket: TicketRead) {
  const { user, can } = useAuth();
  const isStaff = can(Perm.WORK);
  const isRequester = ticket.requester.id === user?.id;
  const notClosed = ticket.status !== "closed";

  let statusTargets: TicketStatus[] = [];
  if (isStaff) statusTargets = NEXT_STATUSES[ticket.status];
  // A requester may only close their own ticket (REQUESTER_STATUS_TARGETS).
  else if (isRequester) statusTargets = NEXT_STATUSES[ticket.status].filter((s) => s === "closed");

  return {
    isStaff,
    statusTargets,
    canClaim: isStaff && notClosed && ticket.assignee?.id !== user?.id,
    // Observers and watchers can read but not take part.
    canComment: isStaff || (isRequester && notClosed),
  };
}

export default function TicketDetailPage() {
  const { id = "" } = useParams();

  const ticket = useQuery({ queryKey: ["tickets", id], queryFn: () => getTicket(id) });

  if (ticket.isPending) return <p className="text-slate-500">Loading ticket…</p>;

  if (ticket.isError) {
   
    const error = ticket.error;
    const notFound = error instanceof ApiError && (error.status === 404 || error.status === 422);
    return (
      <section className="card space-y-3">
        <p className={notFound ? "" : "text-red-700"}>
          {notFound ? "This ticket does not exist, or you are not allowed to see it." : error.message}
        </p>
        <Link to="/tickets" className="text-sm text-blue-700 hover:underline">
          Back to tickets
        </Link>
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <TicketSummary ticket={ticket.data} />
      <TicketActions ticket={ticket.data} />
      <CommentsSection ticket={ticket.data} />
      <AttachmentsSection ticket={ticket.data} />
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase text-slate-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function TicketSummary({ ticket }: { ticket: TicketRead }) {
  const watchers = ticket.watchers ?? [];

  return (
    <section className="card space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-sm text-slate-500">{ticket.reference}</p>
          <h1 className="text-xl font-semibold">{ticket.title}</h1>
        </div>
        <Link to="/tickets" className="text-sm text-blue-700 hover:underline">
          Back to tickets
        </Link>
      </div>

      <div className="flex flex-wrap gap-2">
        <StatusBadge status={ticket.status} />
        <PriorityBadge priority={ticket.priority} />
        {ticket.sla_breached && <span className="badge bg-red-100 text-red-800">SLA breached</span>}
      </div>

      {/* whitespace-pre-wrap keeps the line breaks the requester typed. */}
      <p className="whitespace-pre-wrap text-sm">{ticket.description}</p>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <Fact label="Requester">{ticket.requester.full_name}</Fact>
        <Fact label="Assignee">
          {ticket.assignee?.full_name ?? <span className="text-slate-400">unassigned</span>}
        </Fact>
        <Fact label="Team">{ticket.team.name}</Fact>
        <Fact label="Category">{ticket.category.name}</Fact>
        <Fact label="Created">{formatDate(ticket.created_at)}</Fact>
        <Fact label="SLA due">{formatDate(ticket.sla_due_at)}</Fact>
        {ticket.resolved_at && <Fact label="Resolved">{formatDate(ticket.resolved_at)}</Fact>}
        {ticket.closed_at && <Fact label="Closed">{formatDate(ticket.closed_at)}</Fact>}
        {watchers.length > 0 && (
          <Fact label="Watchers">{watchers.map((w) => w.full_name).join(", ")}</Fact>
        )}
      </dl>
    </section>
  );
}

function TicketActions({ ticket }: { ticket: TicketRead }) {
  const { canClaim, statusTargets } = useAbilities(ticket);
  const queryClient = useQueryClient();
  const [nextStatus, setNextStatus] = useState<TicketStatus | "">("");
  const [note, setNote] = useState("");

  // Status and assignee also show in the list, so refresh every "tickets" key.
  const refreshAll = () => queryClient.invalidateQueries({ queryKey: ["tickets"] });

  const claim = useMutation({
    mutationFn: () => claimTicket(ticket.id),
    onSuccess: refreshAll,
  });

  const move = useMutation({
    mutationFn: (status: TicketStatus) =>
      changeStatus(ticket.id, status, note.trim() || undefined),
    onSuccess: async () => {
      setNextStatus("");
      setNote("");
      await refreshAll();
    },
  });

  if (!canClaim && statusTargets.length === 0) return null;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (nextStatus) move.mutate(nextStatus);
  }

  return (
    <section className="card space-y-3">
      <h2 className="font-semibold">Actions</h2>

      {canClaim && (
        <div className="flex items-center gap-3">
          <button className="btn" onClick={() => claim.mutate()} disabled={claim.isPending}>
            {claim.isPending ? "Claiming…" : "Assign to me"}
          </button>
          {claim.isError && <span className="text-sm text-red-700">{claim.error.message}</span>}
        </div>
      )}

      {statusTargets.length > 0 && (
        <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2">
          <select
            className="input w-44"
            value={nextStatus}
            onChange={(e) => setNextStatus(e.target.value as TicketStatus | "")}
            required
          >
            <option value="">Change status to…</option>
            {statusTargets.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </select>
          <input
            className="input flex-1"
            placeholder="Optional note (saved as a comment)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button className="btn-secondary" type="submit" disabled={move.isPending}>
            {move.isPending ? "Saving…" : "Update"}
          </button>
          {move.isError && <p className="w-full text-sm text-red-700">{move.error.message}</p>}
        </form>
      )}
    </section>
  );
}

function CommentsSection({ ticket }: { ticket: TicketRead }) {
  const { isStaff, canComment } = useAbilities(ticket);
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);

  const comments = useQuery({
    queryKey: ["tickets", ticket.id, "comments"],
    queryFn: () => listComments(ticket.id),
  });

  const post = useMutation({
    mutationFn: () => addComment(ticket.id, body.trim(), internal),
    onSuccess: async () => {
      setBody("");
      setInternal(false);
      // A first staff reply sets first_response_at on the ticket, so refresh
      // the ticket too - ["tickets", id] matches the ticket AND its comments.
      await queryClient.invalidateQueries({ queryKey: ["tickets", ticket.id] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (body.trim()) post.mutate();
  }

  return (
    <section className="card space-y-3">
      <h2 className="font-semibold">Comments</h2>

      {comments.isPending && <p className="text-sm text-slate-500">Loading comments…</p>}
      {comments.isError && <p className="text-sm text-red-700">{comments.error.message}</p>}

      {comments.data && comments.data.items.length === 0 && (
        <p className="text-sm text-slate-500">No comments yet.</p>
      )}

      <ul className="space-y-3">
        {comments.data?.items.map((c) => (
          <li
            key={c.id}
           
            className={`rounded-md border p-3 ${
              c.is_internal ? "border-amber-200 bg-amber-50" : "border-slate-200"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-slate-800">{c.author.full_name}</span>
              <span>{formatDate(c.created_at)}</span>
              {c.edited && <span>(edited)</span>}
              {c.is_internal && <span className="badge bg-amber-100 text-amber-800">internal note</span>}
            </div>
            <p className="mt-1 whitespace-pre-wrap text-sm">{c.body}</p>
          </li>
        ))}
      </ul>

      {canComment ? (
        <form onSubmit={handleSubmit} className="space-y-2">
          <textarea
            className="input min-h-24"
            placeholder="Write a reply"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={10000}
          />
          <div className="flex items-center gap-4">
            <button className="btn" type="submit" disabled={post.isPending || !body.trim()}>
              {post.isPending ? "Posting…" : internal ? "Add internal note" : "Post reply"}
            </button>
            {isStaff && (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={internal}
                  onChange={(e) => setInternal(e.target.checked)}
                />
                Internal note (requester will not see it)
              </label>
            )}
          </div>
          {post.isError && <p className="text-sm text-red-700">{post.error.message}</p>}
        </form>
      ) : (
        <p className="text-sm text-slate-500">
          {ticket.status === "closed" ? "This ticket is closed." : "You can read this ticket but not reply."}
        </p>
      )}
    </section>
  );
}

function AttachmentsSection({ ticket }: { ticket: TicketRead }) {
  const { canComment } = useAbilities(ticket);
  const queryClient = useQueryClient();
  const queryKey = ["tickets", ticket.id, "attachments"];

  const files = useQuery({ queryKey, queryFn: () => listAttachments(ticket.id) });

  const upload = useMutation({
    mutationFn: (file: File) => uploadAttachment(ticket.id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const download = useMutation({ mutationFn: downloadAttachment });

  return (
    <section className="card space-y-3">
      <h2 className="font-semibold">Attachments</h2>

      {files.isPending && <p className="text-sm text-slate-500">Loading files…</p>}
      {files.isError && <p className="text-sm text-red-700">{files.error.message}</p>}
      {files.data && files.data.length === 0 && <p className="text-sm text-slate-500">No files.</p>}

      <ul className="divide-y divide-slate-100 text-sm">
        {files.data?.map((a) => (
          <li key={a.id} className="py-2">
            <button className="text-blue-700 hover:underline" onClick={() => download.mutate(a)}>
              {a.original_filename}
            </button>
            <span className="ml-2 text-xs text-slate-500">
              {a.size_human} · {a.uploader.full_name} · {formatDate(a.created_at)}
            </span>
          </li>
        ))}
      </ul>
      {download.isError && <p className="text-sm text-red-700">{download.error.message}</p>}

      {canComment && (
        <div className="space-y-1">
          <input
            type="file"
            className="text-sm"
            disabled={upload.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              // Clear the input so choosing the same file again still fires onChange.
              e.target.value = "";
            }}
          />
          {upload.isPending && <p className="text-sm text-slate-500">Uploading…</p>}
          {upload.isError && <p className="text-sm text-red-700">{upload.error.message}</p>}
        </div>
      )}
    </section>
  );
}