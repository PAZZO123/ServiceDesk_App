import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import {
  addComment,
  assignTicket,
  changeStatus,
  claimTicket,
  createTag,
  deleteAttachment,
  deleteComment,
  deleteTicket,
  downloadAttachment,
  editComment,
  getTicket,
  listAttachments,
  listCategories,
  listComments,
  listMembers,
  listTags,
  setTicketTags,
  updateTicket,
  uploadCommentAttachment,
  uploadTicketAttachment,
} from "../../api/endpoints";
import type { AttachmentRead, CommentRead, TagBrief, TicketPriority, TicketRead, TicketStatus } from "../../api/types";
import { Perm, useAuth } from "../../auth/auth-context";
import { Avatar, PriorityBadge, SlaBadge, StatusBadge, TagChip } from "../../components/ui/Badges";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Alert, EmptyState, PageLoader } from "../../components/ui/Feedback";
import { SelectField, TextArea, TextField } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage, isStatus } from "../../lib/errors";
import { formatDate, humanize, timeAgo } from "../../lib/format";
import { NEXT_STATUSES, PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from "../../lib/labels";

const REQUESTER_EDITABLE: TicketStatus[] = ["open", "waiting"];

// Mirrors app/core/permissions.py so we only show buttons that will work.
// The server re-checks everything; this is about not offering dead ends.
function useAbilities(ticket: TicketRead | undefined) {
  const { user, can } = useAuth();
  const me = user!.id;
  if (!ticket) return null;
  const staff = can(Perm.WORK);
  const isRequester = ticket.requester.id === me;
  const closed = ticket.status === "closed";
  // Resolved or closed: the record of the fix. Only a moderator (admin) deletes.
  const finished = closed || ticket.status === "resolved";
  const moderate = can(Perm.MODERATE);
  // The requester's own text: only while open or waiting.
  const ownText = isRequester && REQUESTER_EDITABLE.includes(ticket.status);
  // Nobody owns it, I own it, or I may take over (admin).
  const free = !ticket.assignee || ticket.assignee.id === me || can(Perm.REASSIGN);
  return {
    me,
    staff,
    isRequester,
    closed,
    edit: staff || ownText,
    ownText,
    statusTargets: staff ? NEXT_STATUSES[ticket.status] : isRequester ? NEXT_STATUSES[ticket.status].filter((s) => s === "closed") : [],
    // Closed means closed for everyone: no replies, files or (re)assigning.
    comment: !closed && (staff || isRequester),
    internal: staff,
    claim: staff && !closed && ticket.assignee?.id !== me && free,
    assign: staff && !closed && free,
    tags: staff,
    remove: can(Perm.DELETE),
    moderate,
    // Comments and files: mirrors can_delete_comment / can_delete_attachment.
    deleteContent: (authorId: string) => moderate || (authorId === me && !finished),
  };
}

export function TicketDetailPage() {
  const { id = "" } = useParams();
  const ticket = useQuery({ queryKey: ["tickets", id], queryFn: () => getTicket(id) });
  const can = useAbilities(ticket.data);

  if (ticket.isPending) return <PageLoader label="Loading ticket" />;
  if (ticket.isError) {
    return (
      <div className="card">
        <EmptyState
          icon={isStatus(ticket.error, 404, 422) ? "search" : "alert"}
          title={isStatus(ticket.error, 404, 422) ? "Ticket not found" : "Could not load this ticket"}
          text={isStatus(ticket.error, 404, 422) ? "It does not exist, or you are not allowed to see it." : errorMessage(ticket.error)}
          action={<ButtonLink to="/app/tickets" variant="secondary" icon="arrowLeft">Back to tickets</ButtonLink>}
        />
      </div>
    );
  }

  const t = ticket.data;
  return (
    <div className="animate-fade-in">
      <title>{`${t.reference} ${t.title} | ServiceDesk`}</title>
      <Link to="/app/tickets" className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-navy-900">
        <Icon name="arrowLeft" className="size-4" /> Tickets
      </Link>
      <Header ticket={t} can={can!} />
      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_22rem]">
        <div className="min-w-0 space-y-6">
          <Description ticket={t} />
          <Conversation ticket={t} can={can!} />
        </div>
        <div className="space-y-6">
          <Details ticket={t} can={can!} />
          <Attachments ticket={t} can={can!} />
        </div>
      </div>
    </div>
  );
}

type Can = NonNullable<ReturnType<typeof useAbilities>>;

function useTicketMutation<TArgs>(_ticketId: string, fn: (args: TArgs) => Promise<unknown>, success: string) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      // ["tickets"] refreshes this page, the lists and the dashboard.
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      toast(success);
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });
}

// ------------------------------------------------------------------ header

function Header({ ticket, can }: { ticket: TicketRead; can: Can }) {
  const navigate = useNavigate();
  const [statusOpen, setStatusOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const claim = useTicketMutation(ticket.id, () => claimTicket(ticket.id), "You now own this ticket.");
  const queryClient = useQueryClient();
  const toast = useToast();
  const remove = useMutation({
    mutationFn: () => deleteTicket(ticket.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      toast(`${ticket.reference} deleted.`);
      navigate("/app/tickets");
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });

  return (
    <div className="card p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-navy-50 px-2 py-0.5 font-mono text-xs font-medium text-navy-700">{ticket.reference}</span>
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
            <SlaBadge dueAt={ticket.sla_due_at} breached={ticket.sla_breached} done={ticket.status === "resolved" || ticket.status === "closed"} />
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight break-words text-navy-900">{ticket.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Raised by {ticket.requester.full_name} {timeAgo(ticket.created_at)} · {ticket.team.name} · {ticket.category.name}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {can.claim && (
            <Button variant="accent" icon="user" loading={claim.isPending} onClick={() => claim.mutate(undefined)}>
              Claim
            </Button>
          )}
          {can.statusTargets.length > 0 && (
            <Button icon="refresh" onClick={() => setStatusOpen(true)}>
              {can.staff ? "Change status" : "Close ticket"}
            </Button>
          )}
          {can.edit && (
            <Button variant="secondary" icon="edit" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
          )}
          {can.remove && (
            <Button variant="secondary" icon="trash" className="text-red-600 hover:border-red-300 hover:bg-red-50" onClick={() => setDeleteOpen(true)} aria-label="Delete ticket" />
          )}
        </div>
      </div>
      <StatusDialog ticket={ticket} targets={can.statusTargets} open={statusOpen} onClose={() => setStatusOpen(false)} />
      {editOpen && <EditDialog ticket={ticket} staff={can.staff} ownText={can.ownText} onClose={() => setEditOpen(false)} />}
      <ConfirmDialog
        open={deleteOpen}
        title={`Delete ${ticket.reference}?`}
        text="The ticket disappears from every list. It is kept in the database for the audit trail."
        confirmLabel="Delete ticket"
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
        onClose={() => setDeleteOpen(false)}
      />
    </div>
  );
}

function StatusDialog({ ticket, targets, open, onClose }: { ticket: TicketRead; targets: TicketStatus[]; open: boolean; onClose: () => void }) {
  const [target, setTarget] = useState<TicketStatus | "">("");
  const [note, setNote] = useState("");
  const mutation = useTicketMutation(
    ticket.id,
    (args: { status: TicketStatus; note: string }) => changeStatus(ticket.id, args.status, args.note.trim()),
    "Status updated.",
  );
  const chosen = target || targets[0];

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!chosen) return;
    mutation.mutate({ status: chosen, note }, { onSuccess: () => { setNote(""); setTarget(""); onClose(); } });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Change status"
      description={`Currently ${STATUS_LABEL[ticket.status].toLowerCase()}. Only the moves the workflow allows are listed.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="status-form" loading={mutation.isPending}>Save</Button>
        </>
      }
    >
      <form id="status-form" onSubmit={submit} className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          {targets.map((s) => (
            <label key={s} className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-3 text-sm transition ${chosen === s ? "border-navy-700 bg-navy-50 font-medium text-navy-900" : "border-slate-200 hover:border-slate-300"}`}>
              <input type="radio" name="status" className="accent-navy-900" checked={chosen === s} onChange={() => setTarget(s)} />
              {STATUS_LABEL[s]}
            </label>
          ))}
        </div>
        <TextArea label="Note for the requester (optional)" rows={3} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} hint="Added to the conversation as a public comment." />
      </form>
    </Modal>
  );
}

// Staff change only category and priority; title and description are the
// requester's own words (app/core/permissions.py STAFF_EDITABLE_FIELDS).
function EditDialog({ ticket, staff, ownText, onClose }: { ticket: TicketRead; staff: boolean; ownText: boolean; onClose: () => void }) {
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: 300_000, enabled: staff });
  const [title, setTitle] = useState(ticket.title);
  const [description, setDescription] = useState(ticket.description);
  const [priority, setPriority] = useState<TicketPriority>(ticket.priority);
  const [categoryId, setCategoryId] = useState(ticket.category.id);
  const mutation = useTicketMutation(
    ticket.id,
    () => {
      // Send only what changed: requesters may not send staff-only fields.
      const data: Record<string, unknown> = {};
      if (ownText && title.trim() !== ticket.title) data.title = title.trim();
      if (ownText && description.trim() !== ticket.description) data.description = description.trim();
      if (staff && priority !== ticket.priority) data.priority = priority;
      if (staff && categoryId !== ticket.category.id) data.category_id = categoryId;
      return updateTicket(ticket.id, data);
    },
    "Ticket updated.",
  );

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title="Edit ticket"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="edit-form" loading={mutation.isPending}>Save changes</Button>
        </>
      }
    >
      <form
        id="edit-form"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate(undefined, { onSuccess: onClose });
        }}
        className="space-y-4"
      >
        {ownText && (
          <>
            <TextField label="Title" required minLength={5} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextArea label="Description" required minLength={10} rows={6} value={description} onChange={(e) => setDescription(e.target.value)} />
          </>
        )}
        {staff && (
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField label="Priority" value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
              ))}
            </SelectField>
            <SelectField label="Category" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} hint="Moving it hands the ticket to that team, recomputes the SLA and removes an assignee from the old team. Comments stay.">
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </SelectField>
          </div>
        )}
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------- description

function Description({ ticket }: { ticket: TicketRead }) {
  const extra = Object.entries(ticket.extra_data ?? {}).filter(([, v]) => v !== null && v !== "");
  return (
    <section className="card p-6">
      <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">Description</h2>
      <p className="mt-3 text-[15px] leading-relaxed whitespace-pre-wrap text-slate-700">{ticket.description}</p>
      {extra.length > 0 && (
        <dl className="mt-5 grid gap-3 rounded-xl bg-navy-50/60 p-4 sm:grid-cols-2">
          {extra.map(([key, value]) => (
            <div key={key}>
              <dt className="text-xs text-slate-500">{humanize(key)}</dt>
              <dd className="text-sm font-medium text-navy-900">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

// ------------------------------------------------------------ conversation

function Conversation({ ticket, can }: { ticket: TicketRead; can: Can }) {
  const comments = useQuery({ queryKey: ["tickets", ticket.id, "comments"], queryFn: () => listComments(ticket.id) });
  const attachments = useQuery({ queryKey: ["tickets", ticket.id, "attachments"], queryFn: () => listAttachments(ticket.id) });
  const byComment = new Map<string, AttachmentRead[]>();
  for (const a of attachments.data ?? []) {
    if (a.comment_id) byComment.set(a.comment_id, [...(byComment.get(a.comment_id) ?? []), a]);
  }

  return (
    <section className="card">
      <header className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
        <h2 className="font-semibold text-navy-900">Conversation</h2>
        <span className="text-sm text-slate-400">{comments.data ? `${comments.data.total} message${comments.data.total === 1 ? "" : "s"}` : ""}</span>
      </header>
      <div className="space-y-5 px-6 py-5">
        {comments.data?.items.length === 0 && <p className="text-sm text-slate-500">No messages yet. Start the conversation below.</p>}
        {comments.data?.items.map((c) => (
          <CommentItem key={c.id} comment={c} files={byComment.get(c.id) ?? []} can={can} />
        ))}
      </div>
      {can.comment ? <Composer ticket={ticket} internalAllowed={can.internal} /> : (
        <p className="border-t border-slate-100 px-6 py-4 text-sm text-slate-500">
          {ticket.status === "closed" ? "This ticket is closed. Raise a new ticket if the problem returns." : "You can read this ticket but not reply to it."}
        </p>
      )}
    </section>
  );
}

function CommentItem({ comment, files, can }: { comment: CommentRead; files: AttachmentRead[]; can: Can }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(comment.body);
  const [confirm, setConfirm] = useState(false);
  const mine = comment.author.id === can.me;
  const save = useTicketMutation(comment.ticket_id, () => editComment(comment.id, text.trim()), "Comment updated.");
  const remove = useTicketMutation(comment.ticket_id, () => deleteComment(comment.id), "Comment deleted.");

  return (
    <article className={`flex gap-3 ${comment.is_internal ? "rounded-xl border border-amber-200 bg-amber-50/60 p-4" : ""}`}>
      <Avatar name={comment.author.full_name} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-semibold text-navy-900">{comment.author.full_name}</span>
          {comment.is_internal && (
            <span className="chip bg-amber-100 text-amber-800">
              <Icon name="lock" className="size-3" /> Internal note
            </span>
          )}
          <span className="text-xs text-slate-400" title={formatDate(comment.created_at)}>
            {timeAgo(comment.created_at)}
            {comment.edited && " · edited"}
          </span>
          {((mine && !can.closed) || can.deleteContent(comment.author.id)) && !editing && (
            <span className="ml-auto flex gap-1">
              {mine && !can.closed && (
                <button type="button" onClick={() => setEditing(true)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-navy-900" aria-label="Edit comment">
                  <Icon name="edit" className="size-4" />
                </button>
              )}
              {can.deleteContent(comment.author.id) && (
                <button type="button" onClick={() => setConfirm(true)} className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Delete comment">
                  <Icon name="trash" className="size-4" />
                </button>
              )}
            </span>
          )}
        </div>
        {editing ? (
          <form
            className="mt-2 space-y-2"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate(undefined, { onSuccess: () => setEditing(false) });
            }}
          >
            <TextArea rows={3} value={text} onChange={(e) => setText(e.target.value)} required />
            <div className="flex gap-2">
              <Button type="submit" size="sm" loading={save.isPending}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => { setText(comment.body); setEditing(false); }}>Cancel</Button>
            </div>
          </form>
        ) : (
          <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap text-slate-700">{comment.body}</p>
        )}
        {files.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {files.map((f) => (
              <FileChip key={f.id} file={f} />
            ))}
          </div>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        title="Delete this comment?"
        text="The comment and any files attached to it are removed for everyone."
        confirmLabel="Delete"
        loading={remove.isPending}
        onConfirm={() => remove.mutate(undefined, { onSuccess: () => setConfirm(false) })}
        onClose={() => setConfirm(false)}
      />
    </article>
  );
}

function Composer({ ticket, internalAllowed }: { ticket: TicketRead; internalAllowed: boolean }) {
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const send = useMutation({
    mutationFn: async () => {
      const comment = await addComment(ticket.id, body.trim(), internal);
      if (file) await uploadCommentAttachment(comment.id, file);
      return comment;
    },
    onSuccess: () => {
      setBody("");
      setFile(null);
      setInternal(false);
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (body.trim()) send.mutate();
      }}
      className={`border-t px-6 py-5 ${internal ? "border-amber-200 bg-amber-50/50" : "border-slate-100 bg-slate-50/50"}`}
    >
      <TextArea
        rows={3}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        maxLength={10000}
        placeholder={internal ? "Internal note: only staff can see this" : "Write a reply"}
        aria-label="Message"
      />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
          <Icon name="paperclip" className="size-4" />
          <span className="max-w-48 truncate">{file ? file.name : "Attach a file"}</span>
          <input type="file" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        {file && (
          <button type="button" className="text-xs text-slate-400 hover:text-red-600" onClick={() => setFile(null)}>
            Remove
          </button>
        )}
        {internalAllowed && (
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" className="size-4 accent-amber-600" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
            <Icon name="lock" className="size-3.5" /> Internal note
          </label>
        )}
        <Button type="submit" className="ml-auto" icon="message" loading={send.isPending} disabled={!body.trim()}>
          {internal ? "Add note" : "Send"}
        </Button>
      </div>
    </form>
  );
}

// ------------------------------------------------------------------ details

function Details({ ticket, can }: { ticket: TicketRead; can: Can }) {
  const [assignOpen, setAssignOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const rows: [string, ReactNode][] = [
    ["Team", ticket.team.name],
    ["Category", ticket.category.name],
    ["Created", formatDate(ticket.created_at)],
    ["SLA deadline", formatDate(ticket.sla_due_at)],
    ["First response", formatDate(ticket.first_response_at)],
    ["Resolved", formatDate(ticket.resolved_at)],
    ["Closed", formatDate(ticket.closed_at)],
  ];

  return (
    <section className="card p-5">
      <h2 className="font-semibold text-navy-900">Details</h2>
      <div className="mt-4 space-y-4">
        <Person label="Requester" name={ticket.requester.full_name} />
        <div className="flex items-end justify-between gap-2">
          {ticket.assignee ? <Person label="Assignee" name={ticket.assignee.full_name} /> : <div><p className="text-xs text-slate-500">Assignee</p><p className="mt-1 text-sm text-slate-400">Nobody yet</p></div>}
          {can.assign && (
            <Button size="sm" variant="ghost" icon="userPlus" onClick={() => setAssignOpen(true)}>
              {ticket.assignee ? "Reassign" : "Assign"}
            </Button>
          )}
        </div>
        {(ticket.watchers?.length ?? 0) > 0 && (
          <div>
            <p className="text-xs text-slate-500">Watchers</p>
            <div className="mt-1.5 flex -space-x-2">
              {ticket.watchers!.map((w) => (
                <span key={w.id} className="rounded-full ring-2 ring-white">
                  <Avatar name={w.full_name} size="sm" />
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
      <dl className="mt-5 space-y-2.5 border-t border-slate-100 pt-4">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 text-sm">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-right font-medium text-slate-800">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">Tags</p>
          {can.tags && (
            <button type="button" onClick={() => setTagsOpen(true)} className="text-xs font-medium text-navy-700 hover:text-navy-900">
              Edit tags
            </button>
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {(ticket.tags?.length ?? 0) === 0 ? <span className="text-sm text-slate-400">No tags</span> : ticket.tags!.map((tag) => <TagChip key={tag.id} name={tag.name} color={tag.color} />)}
        </div>
      </div>
      {assignOpen && <AssignDialog ticket={ticket} me={can.me} onClose={() => setAssignOpen(false)} />}
      {tagsOpen && <TagsDialog ticket={ticket} onClose={() => setTagsOpen(false)} />}
    </section>
  );
}

function Person({ label, name }: { label: string; name: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <div className="mt-1.5 flex items-center gap-2">
        <Avatar name={name} size="sm" />
        <span className="text-sm font-medium text-navy-900">{name}</span>
      </div>
    </div>
  );
}

function AssignDialog({ ticket, me, onClose }: { ticket: TicketRead; me: string; onClose: () => void }) {
  const members = useQuery({ queryKey: ["teams", ticket.team.id, "members"], queryFn: () => listMembers(ticket.team.id) });
  const [choice, setChoice] = useState(ticket.assignee?.id ?? "");
  const mutation = useTicketMutation(ticket.id, () => assignTicket(ticket.id, choice || null), choice ? "Ticket assigned." : "Ticket unassigned.");

  return (
    <Modal
      open
      onClose={onClose}
      title="Assign ticket"
      description={`Only members of ${ticket.team.name} can own this ticket.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate(undefined, { onSuccess: onClose })}>Save</Button>
        </>
      }
    >
      {members.isError && <Alert>{errorMessage(members.error)}</Alert>}
      <div className="space-y-2">
        <label className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-3 text-sm ${choice === "" ? "border-navy-700 bg-navy-50" : "border-slate-200"}`}>
          <input type="radio" className="accent-navy-900" checked={choice === ""} onChange={() => setChoice("")} />
          <span className="text-slate-600">Nobody (unassign)</span>
        </label>
        {members.data?.map((m) => (
          <label key={m.user.id} className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-3 text-sm ${choice === m.user.id ? "border-navy-700 bg-navy-50" : "border-slate-200"}`}>
            <input type="radio" className="accent-navy-900" checked={choice === m.user.id} onChange={() => setChoice(m.user.id)} />
            <Avatar name={m.user.full_name} size="sm" />
            <span className="flex-1 font-medium text-navy-900">
              {m.user.full_name}
              {m.user.id === me && <span className="ml-1 text-xs font-normal text-slate-400">(you)</span>}
            </span>
            {m.role_in_team === "lead" && <span className="chip bg-leaf-100 text-leaf-700">Lead</span>}
          </label>
        ))}
        {members.data?.length === 0 && <p className="text-sm text-slate-500">This team has no members yet.</p>}
      </div>
    </Modal>
  );
}

// The same palette the seeded tags use.
const TAG_COLORS = ["#DC2626", "#EA580C", "#CA8A04", "#16A34A", "#0891B2", "#2563EB", "#9333EA", "#6B7280"];

// The list comes from GET /tags. The old version collected tags from the
// tickets you can see, so tags that no ticket used yet never appeared and
// the dialog said "No tags exist yet" even with 8 tags in the database.
function TagsDialog({ ticket, onClose }: { ticket: TicketRead; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const tags = useQuery({ queryKey: ["tags"], queryFn: listTags });
  const [chosen, setChosen] = useState<Set<string>>(new Set((ticket.tags ?? []).map((t) => t.id)));
  const mutation = useTicketMutation(ticket.id, () => setTicketTags(ticket.id, [...chosen]), "Tags updated.");

  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(TAG_COLORS[0]);
  const create = useMutation({
    mutationFn: () => createTag(newName, newColor),
    onSuccess: (tag: TagBrief) => {
      void queryClient.invalidateQueries({ queryKey: ["tags"] });
      // A tag you just made is almost always one you want on this ticket.
      setChosen((prev) => new Set(prev).add(tag.id));
      setNewName("");
      toast(`Tag "${tag.name}" created. Press Save tags to keep it on this ticket.`);
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });
  const onCreate = (e: FormEvent) => {
    e.preventDefault();
    if (newName.trim().length >= 2) create.mutate();
  };
  const known = tags.data ?? [];

  return (
    <Modal
      open
      onClose={onClose}
      title="Edit tags"
      description="Tags group related tickets, for example everything about one outage."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate(undefined, { onSuccess: onClose })}>Save tags</Button>
        </>
      }
    >
      {tags.isPending ? (
        <p className="text-sm text-slate-500">Loading tags...</p>
      ) : tags.isError ? (
        <Alert>{errorMessage(tags.error)}</Alert>
      ) : known.length === 0 ? (
        <Alert tone="info">No tags exist yet. Create the first one below.</Alert>
      ) : (
        <div className="flex flex-wrap gap-2">
          {known.map((tag) => {
            const on = chosen.has(tag.id);
            return (
              <button
                key={tag.id}
                type="button"
                onClick={() => {
                  const next = new Set(chosen);
                  if (on) next.delete(tag.id);
                  else next.add(tag.id);
                  setChosen(next);
                }}
                className={`chip px-3 py-1.5 text-sm ring-1 ring-inset transition ${on ? "bg-navy-900 text-white ring-navy-900" : "bg-white text-slate-700 ring-slate-200 hover:ring-navy-600"}`}
              >
                <span className="size-2 rounded-full" style={{ backgroundColor: tag.color }} />
                {tag.name}
                {on && <Icon name="check" className="size-3.5" />}
              </button>
            );
          })}
        </div>
      )}
      <form onSubmit={onCreate} className="mt-5 space-y-3 border-t border-slate-100 pt-4">
        <TextField
          label="New tag"
          hint="For example: printer outage (saved as printer-outage)"
          value={newName}
          maxLength={50}
          onChange={(e) => setNewName(e.target.value)}
        />
        <div className="flex flex-wrap items-center gap-2">
          {TAG_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setNewColor(c)}
              aria-label={`Colour ${c}`}
              aria-pressed={newColor === c}
              className={`size-6 rounded-full ring-offset-2 transition ${newColor === c ? "ring-2 ring-navy-900" : "hover:ring-2 hover:ring-slate-300"}`}
              style={{ backgroundColor: c }}
            />
          ))}
          <Button type="submit" size="sm" variant="secondary" icon="plus" loading={create.isPending} disabled={newName.trim().length < 2} className="ml-auto">
            Create tag
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// -------------------------------------------------------------- attachments

function FileChip({ file }: { file: AttachmentRead }) {
  const toast = useToast();
  return (
    <button
      type="button"
      onClick={() => downloadAttachment(file).catch((err: unknown) => toast(errorMessage(err), "error"))}
      className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:border-navy-600"
    >
      <Icon name="paperclip" className="size-3.5 text-slate-400" />
      <span className="max-w-40 truncate">{file.original_filename}</span>
      <span className="text-slate-400">{file.size_human}</span>
    </button>
  );
}

function Attachments({ ticket, can }: { ticket: TicketRead; can: Can }) {
  const files = useQuery({ queryKey: ["tickets", ticket.id, "attachments"], queryFn: () => listAttachments(ticket.id) });
  const [toDelete, setToDelete] = useState<AttachmentRead | null>(null);
  const toast = useToast();
  const upload = useTicketMutation(ticket.id, (file: File) => uploadTicketAttachment(ticket.id, file), "File uploaded.");
  const remove = useTicketMutation(ticket.id, (id: string) => deleteAttachment(id), "File removed.");

  return (
    <section className="card p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-navy-900">Files</h2>
        {can.comment && (
          <label className="inline-flex cursor-pointer items-center gap-1.5 text-sm font-medium text-navy-700 hover:text-navy-900">
            <Icon name="upload" className="size-4" />
            {upload.isPending ? "Uploading" : "Upload"}
            <input
              type="file"
              className="sr-only"
              disabled={upload.isPending}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) upload.mutate(file);
                e.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      {files.isError && <div className="mt-3"><Alert>{errorMessage(files.error)}</Alert></div>}
      <ul className="mt-4 space-y-2">
        {files.data?.length === 0 && <li className="text-sm text-slate-400">No files yet.</li>}
        {files.data?.map((f) => (
          <li key={f.id} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5">
            <span className="grid size-8 shrink-0 place-items-center rounded-md bg-navy-50 text-navy-700">
              <Icon name="file" className="size-4" />
            </span>
            <button
              type="button"
              onClick={() => downloadAttachment(f).catch((err: unknown) => toast(errorMessage(err), "error"))}
              className="min-w-0 flex-1 text-left"
              title="Download"
            >
              <span className="block truncate text-sm font-medium text-navy-900 hover:underline">{f.original_filename}</span>
              <span className="block text-xs text-slate-400">
                {f.size_human} · {f.uploader.full_name} · {f.comment_id ? "on a comment" : "on the ticket"}
              </span>
            </button>
            {can.deleteContent(f.uploader.id) && (
              <button type="button" onClick={() => setToDelete(f)} className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label={`Delete ${f.original_filename}`}>
                <Icon name="trash" className="size-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={toDelete !== null}
        title="Remove this file?"
        text={toDelete ? `${toDelete.original_filename} is deleted for everyone.` : ""}
        confirmLabel="Remove file"
        loading={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete.id, { onSuccess: () => setToDelete(null) })}
        onClose={() => setToDelete(null)}
      />
    </section>
  );
}
