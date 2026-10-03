import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { changePassword, getReadiness, updateMe, updateMyProfile } from "../../api/endpoints";
import { useAuth } from "../../auth/auth-context";
import { PageHeader, SectionCard } from "../../components/AppBits";
import { Avatar } from "../../components/ui/Badges";
import { Button } from "../../components/ui/Button";
import { Alert } from "../../components/ui/Feedback";
import { SelectField, TextArea, TextField, Toggle } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatDay, humanize } from "../../lib/format";

const TIMEZONES = ["Africa/Kigali", "Africa/Nairobi", "Africa/Kampala", "Africa/Lagos", "Africa/Johannesburg", "Europe/London", "Europe/Paris", "America/New_York", "Asia/Dubai", "UTC"];

export function SettingsPage() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader title="Settings" subtitle="Your profile, preferences and security." />
      <div className="space-y-6">
        <ProfileCard />
        <PreferencesCard />
        <PasswordCard />
        <AccessCard />
        <SystemCard />
      </div>
    </div>
  );
}

function ProfileCard() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user!.full_name);
  const save = useMutation({
    mutationFn: () => updateMe(name.trim()),
    onSuccess: (u) => {
      setUser(u);
      toast("Name updated.");
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });

  return (
    <SectionCard title="Profile">
      <form
        className="flex flex-col gap-6 p-6 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Avatar name={user!.full_name} size="lg" />
        <div className="grid flex-1 gap-4 sm:grid-cols-2">
          <TextField label="Full name" required minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          <TextField label="Email" value={user!.email} disabled hint="Your email is your sign in name and cannot be changed here." />
        </div>
        <Button type="submit" loading={save.isPending} disabled={name.trim() === user!.full_name}>
          Save
        </Button>
      </form>
    </SectionCard>
  );
}

function PreferencesCard() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [timezone, setTimezone] = useState(user!.timezone);
  const [notifyEmail, setNotifyEmail] = useState(user!.notify_email);
  const [notifyInApp, setNotifyInApp] = useState(user!.notify_in_app);
  const [signature, setSignature] = useState(user!.signature ?? "");
  const save = useMutation({
    mutationFn: () => updateMyProfile({ timezone, notify_email: notifyEmail, notify_in_app: notifyInApp, signature: signature.trim() || null }),
    onSuccess: (u) => {
      setUser(u);
      toast("Preferences saved.");
    },
    onError: (err) => toast(errorMessage(err), "error"),
  });
  const zones = TIMEZONES.includes(timezone) ? TIMEZONES : [timezone, ...TIMEZONES];

  return (
    <SectionCard title="Preferences">
      <form
        className="space-y-5 p-6"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="grid gap-5 sm:grid-cols-2">
          <SelectField label="Time zone" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
            {zones.map((z) => (
              <option key={z} value={z}>{z.replace("_", " ")}</option>
            ))}
          </SelectField>
          <TextArea label="Signature" rows={2} maxLength={2000} value={signature} onChange={(e) => setSignature(e.target.value)} placeholder="Amina K. | Network team | ext. 204" />
        </div>
        <div className="space-y-4 rounded-xl border border-slate-200 p-4">
          <Toggle label="Email notifications" description="Get an email when something needs you." checked={notifyEmail} onChange={setNotifyEmail} />
          <Toggle label="In-app notifications" description="Show notifications and the badge in ServiceDesk." checked={notifyInApp} onChange={setNotifyInApp} />
        </div>
        <div className="flex justify-end">
          <Button type="submit" loading={save.isPending}>Save preferences</Button>
        </div>
      </form>
    </SectionCard>
  );
}

function PasswordCard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => changePassword(current, next, confirm),
    onSuccess: async () => {
      toast("Password changed. Please sign in again.");
      // The server ended every session, this one included.
      await logout().catch(() => undefined);
      navigate("/login");
    },
    onError: (err) => setError(errorMessage(err)),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError("The two new passwords do not match.");
      return;
    }
    save.mutate();
  }

  return (
    <SectionCard title="Password">
      <form className="space-y-4 p-6" onSubmit={submit}>
        <Alert tone="info">Changing your password signs you out on every device, this one included.</Alert>
        {error && <Alert>{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-3">
          <TextField label="Current password" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          <TextField label="New password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={next} onChange={(e) => setNext(e.target.value)} />
          <TextField label="Confirm new password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <div className="flex justify-end">
          <Button type="submit" icon="key" loading={save.isPending}>Change password</Button>
        </div>
      </form>
    </SectionCard>
  );
}

function AccessCard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <SectionCard title="Your access">
      <div className="space-y-5 p-6">
        <div className="flex flex-wrap items-center gap-3">
          <span className="chip bg-navy-900 px-3 py-1 text-sm text-white">
            <Icon name="shield" className="size-4 text-leaf-400" />
            {humanize(user!.role.name)}
          </span>
          <span className="text-sm text-slate-500">Member since {formatDay(user!.created_at)}</span>
        </div>
        {user!.role.permissions.length === 0 ? (
          <p className="text-sm text-slate-600">No special permissions: you can raise tickets and follow your own.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {user!.role.permissions.map((p) => (
              <span key={p} className="chip bg-leaf-50 text-leaf-700 ring-1 ring-leaf-500/25 ring-inset">
                <Icon name="check" className="size-3.5" strokeWidth={2.4} />
                {humanize(p)}
              </span>
            ))}
          </div>
        )}
        <div className="border-t border-slate-100 pt-5">
          <Button
            variant="secondary"
            icon="logout"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            Sign out everywhere
          </Button>
          <p className="mt-2 text-xs text-slate-500">Signing out ends your session on all devices.</p>
        </div>
      </div>
    </SectionCard>
  );
}

function SystemCard() {
  const ready = useQuery({ queryKey: ["system", "ready"], queryFn: getReadiness, refetchInterval: 30_000 });
  const ok = ready.data?.status === "ready";
  return (
    <SectionCard title="System status">
      <div className="flex items-center gap-4 p-6">
        <span className={`grid size-11 place-items-center rounded-xl ${ready.isError ? "bg-red-50 text-red-600" : ok ? "bg-leaf-100 text-leaf-700" : "bg-amber-50 text-amber-600"}`}>
          <Icon name="database" />
        </span>
        <div>
          <p className="text-sm font-medium text-navy-900">
            {ready.isPending ? "Checking" : ready.isError ? "API unreachable" : ok ? "All systems operational" : "Database unreachable"}
          </p>
          <p className="text-xs text-slate-500">From GET /health/ready, checked every 30 seconds.</p>
        </div>
      </div>
    </SectionCard>
  );
}
