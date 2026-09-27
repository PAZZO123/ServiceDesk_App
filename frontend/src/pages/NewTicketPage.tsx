import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError } from "../api/client";
import { createTicket, listCategories } from "../api/endpoints";
import type { TicketPriority } from "../api/types";
import { Perm, useAuth } from "../auth/auth-context";

const PRIORITIES: TicketPriority[] = ["low", "medium", "high", "urgent"];

type FieldError = { field: string; message: string };


function errorMessages(error: unknown): string[] {
  if (!(error instanceof ApiError)) return ["Could not reach the server."];
  const fields = (error.details as { fields?: FieldError[] } | undefined)?.fields;
  if (fields && fields.length > 0) {
    return fields.map((f) => `${f.field}: ${f.message}`);
  }
  return [error.message];
}

export default function NewTicketPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const canSetPriority = can(Perm.WORK);

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: listCategories,
    staleTime: Infinity,
  });

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [priority, setPriority] = useState<TicketPriority | "">("");

  const create = useMutation({
    mutationFn: createTicket,
    onSuccess: async (ticket) => {
      await queryClient.invalidateQueries({ queryKey: ["tickets"] });
      navigate("/tickets", { state: { created: ticket.reference } });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate({
      title,
      description,
      category_id: categoryId,
      priority: canSetPriority && priority ? priority : undefined,
    });
  }

  return (
    <section className="card max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">New ticket</h1>
        <Link to="/tickets" className="text-sm text-blue-700 hover:underline">
          Back to tickets
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="grid gap-4">
        <label className="grid gap-1 text-sm">
          Title
          <input
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            minLength={5}
            maxLength={200}
            required
          />
        </label>

        <label className="grid gap-1 text-sm">
          Description
          <textarea
            className="input min-h-32"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What happened, what you expected, what you tried"
            minLength={10}
            maxLength={10000}
            required
          />
        </label>

        <label className="grid gap-1 text-sm">
          Category
          <select
            className="input"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            disabled={categories.isPending}
            required
          >
            <option value="">{categories.isPending ? "Loading…" : "Choose a category"}</option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} (answer within {c.sla_hours}h)
              </option>
            ))}
          </select>
        </label>

        {canSetPriority && (
          <label className="grid gap-1 text-sm">
            Priority
            <select
              className="input"
              value={priority}
              onChange={(e) => setPriority(e.target.value as TicketPriority | "")}
            >
              <option value="">
                Let the system decide ({can(Perm.STARTS_HIGH) ? "high" : "medium"})
              </option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        )}

        {create.isError && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-red-700">
            {errorMessages(create.error).map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}

        <div>
          <button className="btn" type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create ticket"}
          </button>
        </div>
      </form>
    </section>
  );
}