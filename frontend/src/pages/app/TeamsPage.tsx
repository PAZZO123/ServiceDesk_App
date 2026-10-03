import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { addMember, listMembers, listTeams, listUsers, removeMember, setMemberRole } from "../../api/endpoints";
import type { MemberRead, TeamRole } from "../../api/types";
import { Perm, useAuth } from "../../auth/auth-context";
import { PageHeader } from "../../components/AppBits";
import { Avatar } from "../../components/ui/Badges";
import { Button } from "../../components/ui/Button";
import { Alert, EmptyState, Skeleton } from "../../components/ui/Feedback";
import { SelectField, TextField } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatDay } from "../../lib/format";

export function TeamsPage() {
  const { can } = useAuth();
  const manage = can(Perm.TEAM_MANAGE);
  const teams = useQuery({ queryKey: ["teams"], queryFn: listTeams, staleTime: 300_000 });
  const [selected, setSelected] = useState<string | null>(null);
  const teamId = selected ?? teams.data?.[0]?.id ?? null;
  const team = teams.data?.find((t) => t.id === teamId);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Teams" subtitle={manage ? "Who works which queue. Members see their team's tickets." : "Who works which queue."} />
      {teams.isError && <Alert>{errorMessage(teams.error)}</Alert>}
      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <div className="card h-fit p-2">
          {teams.isPending &&
            [1, 2, 3, 4].map((n) => (
              <div key={n} className="p-2">
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          {teams.data?.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSelected(t.id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition ${t.id === teamId ? "bg-navy-900 text-white" : "hover:bg-slate-50"}`}
            >
              <span className={`grid size-9 place-items-center rounded-lg ${t.id === teamId ? "bg-white/10 text-leaf-400" : "bg-navy-50 text-navy-700"}`}>
                <Icon name="users" className="size-4.5" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{t.name}</span>
                <span className={`block text-xs ${t.id === teamId ? "text-white/50" : "text-slate-400"}`}>{t.slug}</span>
              </span>
            </button>
          ))}
        </div>
        {team ? <Members teamId={team.id} teamName={team.name} manage={manage} /> : !teams.isPending && <div className="card"><EmptyState title="No teams yet" /></div>}
      </div>
    </div>
  );
}

function Members({ teamId, teamName, manage }: { teamId: string; teamName: string; manage: boolean }) {
  const members = useQuery({ queryKey: ["teams", teamId, "members"], queryFn: () => listMembers(teamId) });
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<MemberRead | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["teams", teamId] });

  const role = useMutation({
    mutationFn: ({ userId, value }: { userId: string; value: TeamRole }) => setMemberRole(teamId, userId, value),
    onSuccess: () => {
      refresh();
      toast("Role in team updated.");
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });
  const remove = useMutation({
    mutationFn: (userId: string) => removeMember(teamId, userId),
    onSuccess: (res) => {
      refresh();
      setRemoving(null);
      toast(
        res.open_tickets_still_assigned
          ? `Removed. ${res.open_tickets_still_assigned} open ticket(s) are still assigned to them: reassign them.`
          : "Member removed.",
        res.open_tickets_still_assigned ? "info" : "success",
      );
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });

  return (
    <section className="card overflow-hidden">
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="font-semibold text-navy-900">{teamName}</h2>
          <p className="text-xs text-slate-500">{members.data ? `${members.data.length} member${members.data.length === 1 ? "" : "s"}` : ""}</p>
        </div>
        {manage && (
          <Button icon="userPlus" size="sm" onClick={() => setAdding(true)}>
            Add member
          </Button>
        )}
      </header>
      {members.isPending ? (
        <div className="space-y-3 p-5">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : members.data?.length === 0 ? (
        <EmptyState icon="users" title="No members yet" text="Add agents so this team's tickets have someone to work them." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {members.data?.map((m) => (
            <li key={m.user.id} className="flex flex-wrap items-center gap-4 px-5 py-3.5">
              <Avatar name={m.user.full_name} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-navy-900">{m.user.full_name}</p>
                <p className="text-xs text-slate-400">Joined {formatDay(m.joined_at)}</p>
              </div>
              {manage ? (
                <select
                  value={m.role_in_team}
                  onChange={(e) => role.mutate({ userId: m.user.id, value: e.target.value as TeamRole })}
                  className="field w-auto py-1.5"
                  aria-label={`Role of ${m.user.full_name} in the team`}
                >
                  <option value="member">Member</option>
                  <option value="lead">Lead</option>
                </select>
              ) : (
                <span className={`chip ${m.role_in_team === "lead" ? "bg-leaf-100 text-leaf-700" : "bg-slate-100 text-slate-600"}`}>
                  {m.role_in_team === "lead" ? "Lead" : "Member"}
                </span>
              )}
              {manage && (
                <button type="button" onClick={() => setRemoving(m)} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label={`Remove ${m.user.full_name}`}>
                  <Icon name="trash" className="size-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {adding && <AddMemberDialog teamId={teamId} teamName={teamName} existing={new Set(members.data?.map((m) => m.user.id))} onClose={() => setAdding(false)} />}
      <ConfirmDialog
        open={removing !== null}
        title={`Remove ${removing?.user.full_name ?? ""}?`}
        text={`They will stop seeing ${teamName}'s queue. Tickets already assigned to them stay assigned.`}
        confirmLabel="Remove"
        loading={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.user.id)}
        onClose={() => setRemoving(null)}
      />
    </section>
  );
}

function AddMemberDialog({ teamId, teamName, existing, onClose }: { teamId: string; teamName: string; existing: Set<string>; onClose: () => void }) {
  const { can } = useAuth();
  // Listing users needs user.manage. Without it, paste the user's id.
  const canList = can(Perm.USER_MANAGE);
  const users = useQuery({ queryKey: ["users", "all"], queryFn: () => listUsers(1, 100), enabled: canList });
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<TeamRole>("member");
  const queryClient = useQueryClient();
  const toast = useToast();
  const add = useMutation({
    mutationFn: () => addMember(teamId, userId.trim(), role),
    onSuccess: (m) => {
      void queryClient.invalidateQueries({ queryKey: ["teams", teamId] });
      toast(`${m.user.full_name} joined ${teamName}.`);
      onClose();
    },
  });

  // Only staff can be team members (the API answers 400 otherwise).
  const candidates = users.data?.items.filter((u) => !existing.has(u.id) && u.role.permissions.includes(Perm.WORK)) ?? [];

  function submit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Add a member to ${teamName}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="add-member" loading={add.isPending} disabled={!userId}>Add member</Button>
        </>
      }
    >
      <form id="add-member" onSubmit={submit} className="space-y-4">
        {add.isError && <Alert>{errorMessage(add.error)}</Alert>}
        {canList ? (
          <SelectField label="Person" value={userId} onChange={(e) => setUserId(e.target.value)} required hint="Only support staff can join a team.">
            <option value="" disabled>
              {users.isPending ? "Loading people" : candidates.length ? "Choose someone" : "Nobody left to add"}
            </option>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </SelectField>
        ) : (
          <TextField label="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} required placeholder="00000000-0000-0000-0000-000000000000" hint="You cannot list users, so paste the person's ID." />
        )}
        <SelectField label="Role in team" value={role} onChange={(e) => setRole(e.target.value as TeamRole)}>
          <option value="member">Member</option>
          <option value="lead">Lead</option>
        </SelectField>
      </form>
    </Modal>
  );
}
