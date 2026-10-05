import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { assignRole, listRoles, listUsers, setUserActive } from "../../api/endpoints";
import type { UserRead } from "../../api/types";
import { Perm, useAuth } from "../../auth/auth-context";
import { PageHeader } from "../../components/AppBits";
import { Avatar } from "../../components/ui/Badges";
import { Button } from "../../components/ui/Button";
import { Alert, Skeleton } from "../../components/ui/Feedback";
import { Icon } from "../../components/ui/Icon";
import { ConfirmDialog } from "../../components/ui/Modal";
import { Pagination } from "../../components/ui/Pagination";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatDay, humanize } from "../../lib/format";

const SIZE = 20;

export function UsersPage() {
  const { user: me } = useAuth();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [pending, setPending] = useState<{ user: UserRead; role: string } | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();

  const users = useQuery({ queryKey: ["users", page], queryFn: () => listUsers(page, SIZE), placeholderData: keepPreviousData });
  const roles = useQuery({ queryKey: ["roles"], queryFn: listRoles });

  const change = useMutation({
    mutationFn: ({ user, role }: { user: UserRead; role: string }) => assignRole(user.id, role),
    onSuccess: (u) => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      toast(`${u.full_name} is now ${humanize(u.role.name)}.`);
      setPending(null);
    },
    onError: (err) => {
      toast(errorMessage(err), "error");
      setPending(null);
    },
  });

  // Disable / enable. Mirrors RoleService.set_active: never yourself, and
  // only someone whose role has no power you lack (ticket.starts_high is a
  // setting, not a power). The server checks again; this hides dead buttons.
  const [toggling, setToggling] = useState<UserRead | null>(null);
  const myPerms = new Set<string>(me?.role.permissions ?? []);
  const mayToggle = (u: UserRead) =>
    u.id !== me?.id && u.role.permissions.every((p) => myPerms.has(p) || p === Perm.STARTS_HIGH);
  const access = useMutation({
    mutationFn: (u: UserRead) => setUserActive(u.id, !u.is_active),
    onSuccess: (u) => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      toast(u.is_active ? `${u.full_name} can sign in again.` : `${u.full_name} is disabled and signed out everywhere.`);
      setToggling(null);
    },
    onError: (err) => {
      toast(errorMessage(err), "error");
      setToggling(null);
    },
  });

  const shown = (users.data?.items ?? []).filter((u) => {
    const q = filter.trim().toLowerCase();
    return !q || u.full_name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Users" subtitle="Everyone with an account, and the role that decides what they can do." />
      {users.isError && <Alert>{errorMessage(users.error)}</Alert>}
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
          <div className="relative w-full sm:w-72">
            <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter this page by name or email" className="field pl-9" aria-label="Filter users" />
          </div>
          <p className="text-sm text-slate-500">{users.data ? `${users.data.total} people` : ""}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[840px]">
            <thead className="bg-slate-50/80">
              <tr>
                <th className="table-head">Person</th>
                <th className="table-head">Status</th>
                <th className="table-head">Joined</th>
                <th className="table-head">Role</th>
                <th className="table-head">Access</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.isPending &&
                [1, 2, 3].map((n) => (
                  <tr key={n}>
                    <td colSpan={5} className="p-4">
                      <Skeleton className="h-10 w-full" />
                    </td>
                  </tr>
                ))}
              {shown.map((u) => (
                <tr key={u.id} className="hover:bg-navy-50/40">
                  <td className="table-cell">
                    <div className="flex items-center gap-3">
                      <Avatar name={u.full_name} />
                      <div className="min-w-0">
                        <p className="truncate font-medium text-navy-900">
                          {u.full_name}
                          {u.id === me?.id && <span className="ml-1.5 text-xs font-normal text-slate-400">(you)</span>}
                        </p>
                        <p className="truncate text-xs text-slate-500">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="table-cell">
                    <div className="flex flex-wrap gap-1.5">
                      <span className={`chip ${u.is_active ? "bg-leaf-100 text-leaf-700" : "bg-slate-100 text-slate-500"}`}>{u.is_active ? "Active" : "Disabled"}</span>
                      {!u.is_verified && <span className="chip bg-amber-50 text-amber-700">Unverified</span>}
                    </div>
                  </td>
                  <td className="table-cell text-slate-500">{formatDay(u.created_at)}</td>
                  <td className="table-cell">
                    <select
                      className="field w-48 py-1.5"
                      value={u.role.name}
                      disabled={u.id === me?.id || change.isPending}
                      title={u.id === me?.id ? "Nobody can change their own role" : undefined}
                      onChange={(e) => setPending({ user: u, role: e.target.value })}
                      aria-label={`Role of ${u.full_name}`}
                    >
                      {(roles.data ?? [{ name: u.role.name, id: "current" }]).map((r) => (
                        <option key={r.id} value={r.name}>
                          {humanize(r.name)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="table-cell">
                    <Button
                      size="sm"
                      variant={u.is_active ? "ghost" : "secondary"}
                      icon={u.is_active ? "lock" : "check"}
                      className={u.is_active ? "text-red-600 hover:bg-red-50" : ""}
                      disabled={!mayToggle(u) || access.isPending}
                      title={
                        u.id === me?.id
                          ? "Nobody can disable their own account"
                          : mayToggle(u)
                            ? undefined
                            : "This user has permissions you do not have"
                      }
                      onClick={() => setToggling(u)}
                    >
                      {u.is_active ? "Disable" : "Enable"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {users.data && <Pagination page={page} pages={users.data.pages} total={users.data.total} size={SIZE} onChange={setPage} />}
      </div>
      <ConfirmDialog
        open={pending !== null}
        danger={false}
        title="Change role?"
        text={
          pending && (
            <>
              <b className="text-navy-900">{pending.user.full_name}</b> goes from {humanize(pending.user.role.name)} to{" "}
              <b className="text-navy-900">{humanize(pending.role)}</b>. Their access changes on their next request.
            </>
          )
        }
        confirmLabel="Change role"
        loading={change.isPending}
        onConfirm={() => pending && change.mutate(pending)}
        onClose={() => setPending(null)}
      />
      <ConfirmDialog
        open={toggling !== null}
        danger={toggling?.is_active ?? true}
        title={toggling?.is_active ? "Disable this account?" : "Enable this account?"}
        text={
          toggling &&
          (toggling.is_active ? (
            <>
              <b className="text-navy-900">{toggling.full_name}</b> is signed out on every device at once and cannot sign in until an
              administrator enables the account again. Their tickets and comments stay.
            </>
          ) : (
            <>
              <b className="text-navy-900">{toggling.full_name}</b> can sign in again with their password. Old sessions stay ended.
            </>
          ))
        }
        confirmLabel={toggling?.is_active ? "Disable account" : "Enable account"}
        loading={access.isPending}
        onConfirm={() => toggling && access.mutate(toggling)}
        onClose={() => setToggling(null)}
      />
      <p className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-400">
        <Icon name="info" className="size-3.5" /> You cannot change your own role. Ask another administrator.
      </p>
    </div>
  );
}
