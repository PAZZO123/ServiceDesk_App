import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { createRole, deleteRole, listPermissions, listRoles, setRolePermissions } from "../../api/endpoints";
import type { PermissionCode, PermissionRead, RoleRead } from "../../api/types";
import { Perm, useAuth } from "../../auth/auth-context";
import { PageHeader } from "../../components/AppBits";
import { Button } from "../../components/ui/Button";
import { Alert, Skeleton } from "../../components/ui/Feedback";
import { TextField } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { humanize } from "../../lib/format";

// Same rule as app/services/role_service.py: this one is a setting, not a
// power, so anyone with role.manage may grant it.
const NOT_A_POWER = new Set<string>([Perm.STARTS_HIGH]);

export function RolesPage() {
  const { user, can } = useAuth();
  const manage = can(Perm.ROLE_MANAGE);
  const roles = useQuery({ queryKey: ["roles"], queryFn: listRoles });
  const permissions = useQuery({ queryKey: ["permissions"], queryFn: listPermissions, staleTime: Infinity });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<RoleRead | null>(null);
  const [deleting, setDeleting] = useState<RoleRead | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();

  const remove = useMutation({
    mutationFn: (role: RoleRead) => deleteRole(role.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast("Role deleted.");
      setDeleting(null);
    },
    onError: (err) => {
      toast(errorMessage(err), "error");
      setDeleting(null);
    },
  });

  const describe = new Map(permissions.data?.map((p) => [p.code, p.description]));

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Roles & permissions"
        subtitle="A role is a set of permissions. Give someone a role on the Users page."
        actions={manage && (
          <Button icon="plus" onClick={() => setCreating(true)}>
            New role
          </Button>
        )}
      />
      {!manage && (
        <div className="mb-6">
          <Alert tone="info">You can see the roles, but changing them needs the role.manage permission.</Alert>
        </div>
      )}
      {roles.isError && <Alert>{errorMessage(roles.error)}</Alert>}

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {roles.isPending && [1, 2, 3].map((n) => <Skeleton key={n} className="h-56 w-full rounded-xl" />)}
        {roles.data?.map((role) => {
          const mine = role.name === user?.role.name;
          return (
            <article key={role.id} className="card flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-navy-900">{humanize(role.name)}</h2>
                  <p className="mt-0.5 text-sm text-slate-500">{role.description || "No description"}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  {role.is_system && <span className="chip bg-navy-50 text-navy-700">Built in</span>}
                  {mine && <span className="chip bg-leaf-100 text-leaf-700">Your role</span>}
                </div>
              </div>
              <ul className="mt-4 flex-1 space-y-2">
                {role.permissions.length === 0 && <li className="text-sm text-slate-400">No special permissions. Can raise and follow own tickets.</li>}
                {role.permissions.map((code) => (
                  <li key={code} className="flex items-start gap-2 text-sm" title={describe.get(code as PermissionCode)}>
                    <Icon name="check" className="mt-0.5 size-4 shrink-0 text-leaf-500" strokeWidth={2.4} />
                    <span>
                      <span className="font-medium text-slate-800">{humanize(code)}</span>
                      {describe.get(code as PermissionCode) && <span className="block text-xs text-slate-500">{describe.get(code as PermissionCode)}</span>}
                    </span>
                  </li>
                ))}
              </ul>
              {manage && (
                <div className="mt-5 flex gap-2 border-t border-slate-100 pt-4">
                  <Button
                    size="sm"
                    variant="secondary"
                    icon="edit"
                    disabled={mine}
                    title={mine ? "Nobody can edit the permissions of their own role" : undefined}
                    onClick={() => setEditing(role)}
                  >
                    Edit permissions
                  </Button>
                  {!role.is_system && (
                    <Button size="sm" variant="ghost" icon="trash" className="text-red-600 hover:bg-red-50" onClick={() => setDeleting(role)}>
                      Delete
                    </Button>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {creating && permissions.data && <RoleDialog permissions={permissions.data} onClose={() => setCreating(false)} />}
      {editing && permissions.data && <RoleDialog role={editing} permissions={permissions.data} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={deleting !== null}
        title={`Delete the ${deleting ? humanize(deleting.name) : ""} role?`}
        text="Only possible when nobody has this role. Built-in roles cannot be deleted."
        confirmLabel="Delete role"
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}

function RoleDialog({ role, permissions, onClose }: { role?: RoleRead; permissions: PermissionRead[]; onClose: () => void }) {
  const { user } = useAuth();
  const mine = new Set(user?.role.permissions ?? []);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [chosen, setChosen] = useState<Set<PermissionCode>>(new Set((role?.permissions ?? []) as PermissionCode[]));
  const queryClient = useQueryClient();
  const toast = useToast();

  const save = useMutation({
    mutationFn: () => (role ? setRolePermissions(role.id, [...chosen]) : createRole(name.trim(), description.trim(), [...chosen])),
    onSuccess: (r) => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast(role ? `${humanize(r.name)} updated.` : `${humanize(r.name)} created.`);
      onClose();
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={role ? `Permissions of ${humanize(role.name)}` : "New role"}
      description="You can only grant or remove permissions you hold yourself. Every change is audited."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="role-form" loading={save.isPending}>{role ? "Save permissions" : "Create role"}</Button>
        </>
      }
    >
      <form id="role-form" onSubmit={submit} className="space-y-5">
        {save.isError && <Alert>{errorMessage(save.error)}</Alert>}
        {!role && (
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Name"
              required
              minLength={2}
              maxLength={50}
              pattern="[a-z][a-z0-9_]*"
              value={name}
              onChange={(e) => setName(e.target.value.toLowerCase().replace(/[\s-]+/g, "_"))}
              placeholder="senior_agent"
              hint="Lowercase letters, digits and underscores."
            />
            <TextField label="Description" maxLength={255} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Agents who may also delete tickets" />
          </div>
        )}
        <div className="grid gap-2 sm:grid-cols-2">
          {permissions.map((p) => {
            const on = chosen.has(p.code as PermissionCode);
            const allowed = mine.has(p.code) || NOT_A_POWER.has(p.code);
            return (
              <label
                key={p.code}
                className={`flex gap-3 rounded-lg border p-3.5 transition ${allowed ? "cursor-pointer" : "cursor-not-allowed opacity-50"} ${on ? "border-navy-700 bg-navy-50" : "border-slate-200 hover:border-slate-300"}`}
                title={allowed ? undefined : "You do not hold this permission, so you cannot grant or remove it"}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-navy-900"
                  checked={on}
                  disabled={!allowed}
                  onChange={() => {
                    const next = new Set(chosen);
                    if (on) next.delete(p.code as PermissionCode);
                    else next.add(p.code as PermissionCode);
                    setChosen(next);
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-navy-900">{humanize(p.code)}</span>
                  <span className="block text-xs text-slate-500">{p.description}</span>
                </span>
              </label>
            );
          })}
        </div>
      </form>
    </Modal>
  );
}
