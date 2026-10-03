import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { createTicket, listCategories, uploadTicketAttachment } from "../../api/endpoints";
import type { TicketPriority } from "../../api/types";
import { Perm, useAuth } from "../../auth/auth-context";
import { PageHeader } from "../../components/AppBits";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Alert, Skeleton } from "../../components/ui/Feedback";
import { SelectField, TextArea, TextField } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatHours } from "../../lib/format";
import { PRIORITIES, PRIORITY_LABEL } from "../../lib/labels";

export function NewTicketPage() {
  const { can } = useAuth();
  const staff = can(Perm.WORK);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: 300_000 });

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [priority, setPriority] = useState<TicketPriority | "">("");
  const [location, setLocation] = useState("");
  const [device, setDevice] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  const create = useMutation({
    mutationFn: async () => {
      const extra: Record<string, string> = {};
      if (location.trim()) extra.location = location.trim();
      if (device.trim()) extra.device = device.trim();
      const ticket = await createTicket({
        title: title.trim(),
        description: description.trim(),
        category_id: categoryId,
        // Only staff may choose; for everyone else the field is not sent.
        priority: staff && priority ? priority : undefined,
        extra_data: extra,
      });
      const failed: string[] = [];
      for (const file of files) {
        try {
          await uploadTicketAttachment(ticket.id, file);
        } catch {
          failed.push(file.name);
        }
      }
      return { ticket, failed };
    },
    onSuccess: ({ ticket, failed }) => {
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      toast(`${ticket.reference} raised. The ${ticket.team.name} team has been notified.`);
      if (failed.length) toast(`Could not attach: ${failed.join(", ")}`, "error");
      navigate(`/app/tickets/${ticket.id}`);
    },
  });

  const selected = categories.data?.find((c) => c.id === categoryId);

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader title="Raise a ticket" subtitle="Describe the problem once. We route it to the right team." actions={<ButtonLink to="/app/tickets" variant="ghost" icon="arrowLeft">Back to tickets</ButtonLink>} />

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="card space-y-5 p-6">
          {create.isError && <Alert>{errorMessage(create.error)}</Alert>}
          <TextField label="Title" required minLength={5} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Short summary, e.g. VPN disconnects every few minutes" />
          <TextArea
            label="Description"
            required
            minLength={10}
            maxLength={10000}
            rows={7}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What happened, what you expected, and what you already tried."
            hint={`${description.length} / 10000`}
          />
          {categories.isPending ? (
            <Skeleton className="h-11 w-full" />
          ) : (
            <SelectField label="Category" required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} hint="The category decides which team gets the ticket and its deadline.">
              <option value="" disabled>
                Choose a category
              </option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </SelectField>
          )}
          <div className="grid gap-5 sm:grid-cols-2">
            <TextField label="Location (optional)" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Floor 2, room 204" />
            <TextField label="Device or asset (optional)" value={device} onChange={(e) => setDevice(e.target.value)} placeholder="e.g. HP printer PR-07" />
          </div>
          {staff && (
            <SelectField label="Priority" value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority | "")} hint="Leave empty to use the default for your role.">
              <option value="">Default</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABEL[p]}
                </option>
              ))}
            </SelectField>
          )}

          <div>
            <span className="label">Attachments (optional)</span>
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 px-6 py-8 text-center transition hover:border-navy-600 hover:bg-navy-50/50">
              <Icon name="upload" className="size-6 text-navy-700" />
              <span className="mt-2 text-sm font-medium text-navy-900">Click to add screenshots or documents</span>
              <span className="mt-1 text-xs text-slate-500">PNG, JPG, GIF, WEBP, PDF, TXT, CSV, ZIP, DOCX, XLSX. Up to 10 MB each.</span>
              <input type="file" multiple className="sr-only" onChange={(e) => setFiles([...files, ...Array.from(e.target.files ?? [])])} />
            </label>
            {files.length > 0 && (
              <ul className="mt-3 space-y-2">
                {files.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                    <Icon name="file" className="size-4 text-slate-400" />
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="text-xs text-slate-400">{(f.size / 1024).toFixed(0)} KB</span>
                    <button type="button" onClick={() => setFiles(files.filter((_, j) => j !== i))} className="text-slate-400 hover:text-red-600" aria-label={`Remove ${f.name}`}>
                      <Icon name="x" className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <ButtonLink to="/app/tickets" variant="secondary">
              Cancel
            </ButtonLink>
            <Button type="submit" loading={create.isPending} icon="check">
              Submit ticket
            </Button>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="card p-5">
            <p className="text-sm font-semibold text-navy-900">What happens next</p>
            <ol className="mt-4 space-y-4">
              {[
                ["The right team is notified", selected ? "Based on the category you chose." : "Based on the category you choose."],
                ["A deadline is set", selected ? `This category has a ${formatHours(selected.sla_hours)} SLA.` : "Each category has its own SLA."],
                ["You follow it live", "Comments and status changes appear without refreshing."],
              ].map(([head, text], i) => (
                <li key={head} className="flex gap-3">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-navy-900 text-xs font-semibold text-leaf-400">{i + 1}</span>
                  <span>
                    <span className="block text-sm font-medium text-slate-800">{head}</span>
                    <span className="block text-xs text-slate-500">{text}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div className="rounded-xl bg-leaf-50 p-5 text-sm text-leaf-700">
            <p className="font-semibold">Tip</p>
            <p className="mt-1">A screenshot of the error message saves the agent a round trip.</p>
          </div>
        </aside>
      </form>
    </div>
  );
}
