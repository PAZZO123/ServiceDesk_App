import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { getTicketByReference } from "../api/endpoints";
import { Perm, useAuth, type PermissionName } from "../auth/auth-context";
import { Avatar } from "../components/ui/Badges";
import { ButtonLink } from "../components/ui/Button";
import { Icon, type IconName } from "../components/ui/Icon";
import { Logo } from "../components/ui/Logo";
import { ConfirmDialog } from "../components/ui/Modal";
import { useToast } from "../components/ui/toast-context";
import { humanize } from "../lib/format";
import { useLiveUpdates, type LiveStatus } from "../realtime/useLiveUpdates";
import { useUnreadCount } from "../realtime/useUnreadCount";

type NavItem = {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  // Shown when the user has ANY of these (empty = everyone).
  any?: PermissionName[];
};

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Workspace",
    items: [
      { to: "/app", label: "Dashboard", icon: "grid", end: true },
      { to: "/app/tickets", label: "Tickets", icon: "ticket" },
      { to: "/app/activity", label: "Activity", icon: "activity" },
      { to: "/app/notifications", label: "Notifications", icon: "bell" },
    ],
  },
  {
    section: "Insights",
    items: [{ to: "/app/analytics", label: "Analytics", icon: "chart", any: [Perm.VIEW_ALL] }],
  },
  {
    section: "Administration",
    items: [
      { to: "/app/teams", label: "Teams", icon: "users", any: [Perm.WORK, Perm.TEAM_MANAGE, Perm.VIEW_ALL] },
      { to: "/app/users", label: "Users", icon: "user", any: [Perm.USER_MANAGE] },
      { to: "/app/roles", label: "Roles & permissions", icon: "shield", any: [Perm.USER_MANAGE, Perm.ROLE_MANAGE] },
    ],
  },
];

const LIVE: Record<LiveStatus, { dot: string; text: string }> = {
  live: { dot: "bg-leaf-500", text: "Live" },
  connecting: { dot: "bg-amber-400 animate-pulse", text: "Connecting" },
  offline: { dot: "bg-red-500", text: "Offline" },
};

export function AppLayout() {
  const { user, can, logout } = useAuth();
  const live = useLiveUpdates();
  const unread = useUnreadCount();
  const [drawer, setDrawer] = useState(false);
  // Sign out is one click from the sidebar and ends EVERY session (the
  // backend revokes all refresh tokens), so it asks first.
  const [confirmSignOut, setConfirmSignOut] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  if (!user) return null;

  const sections = NAV.map((s) => ({
    ...s,
    items: s.items.filter((item) => !item.any || item.any.some((p) => can(p))),
  })).filter((s) => s.items.length > 0);

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5">
        <Link to="/app">
          <Logo light />
        </Link>
      </div>
      <div className="px-4 pt-2">
        <ButtonLink to="/app/tickets/new" variant="accent" icon="plus" className="w-full" onClick={() => setDrawer(false)}>
          New ticket
        </ButtonLink>
      </div>
      <nav className="mt-6 flex-1 space-y-6 overflow-y-auto px-3">
        {sections.map((section) => (
          <div key={section.section}>
            <p className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-white/40 uppercase">{section.section}</p>
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={() => setDrawer(false)}
                    className={({ isActive }) =>
                      `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                        isActive ? "bg-white/10 font-medium text-white" : "text-white/65 hover:bg-white/5 hover:text-white"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon name={item.icon} className={`size-4.5 ${isActive ? "text-leaf-400" : ""}`} />
                        <span className="flex-1">{item.label}</span>
                        {item.to === "/app/notifications" && unread !== null && unread > 0 && (
                          <span className="rounded-full bg-leaf-500 px-2 py-0.5 text-[11px] font-semibold text-navy-950">
                            {unread > 99 ? "99+" : unread}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="m-3 rounded-xl bg-white/5 p-3">
        <div className="flex items-center gap-3">
          <Avatar name={user.full_name} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
            <p className="truncate text-xs text-white/50">{humanize(user.role.name)}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              setDrawer(false);
              setConfirmSignOut(true);
            }}
            className="rounded-lg p-2 text-white/60 hover:bg-white/10 hover:text-white"
            title="Sign out"
            aria-label="Sign out"
          >
            <Icon name="logout" className="size-4.5" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-navy-900 lg:block">{sidebar}</aside>

      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-navy-950/50" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 animate-fade-in bg-navy-900">{sidebar}</aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200/80 bg-white/85 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setDrawer(true)}
            aria-label="Open menu"
          >
            <Icon name="menu" />
          </button>
          <ReferenceSearch />
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <span className="hidden items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 sm:inline-flex" title="Live updates connection">
              <span className={`size-2 rounded-full ${LIVE[live].dot}`} />
              {LIVE[live].text}
            </span>
            <Link to="/app/notifications" className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label="Notifications">
              <Icon name="bell" />
              {unread !== null && unread > 0 && (
                <span className="absolute top-1 right-1 grid min-w-4.5 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </Link>
            <Link to="/app/settings" className="rounded-full" aria-label="Your settings">
              <Avatar name={user.full_name} />
            </Link>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>

      {/* Rendered once here, not inside {sidebar}, which is drawn twice. */}
      <ConfirmDialog
        open={confirmSignOut}
        danger={false}
        title="Sign out?"
        text="You will be signed out on every device where you are signed in."
        confirmLabel="Sign out"
        loading={signingOut}
        onConfirm={async () => {
          setSigningOut(true);
          try {
            await logout();
          } finally {
            setSigningOut(false);
            setConfirmSignOut(false);
          }
        }}
        onClose={() => setConfirmSignOut(false)}
      />
    </div>
  );
}

// Jump straight to a ticket by its reference (GET /tickets/reference/{ref}).
function ReferenceSearch() {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);

  // Press "/" anywhere to focus the box, like most web apps.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        e.preventDefault();
        input.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = value.trim();
    if (!text) return;
    if (!/^TCK-\d{4}-\d+$/i.test(text)) {
      navigate(`/app/tickets?q=${encodeURIComponent(text)}&sort=relevance`);
      setValue("");
      return;
    }
    setBusy(true);
    try {
      const ticket = await getTicketByReference(text);
      navigate(`/app/tickets/${ticket.id}`);
      setValue("");
    } catch {
      toast(`No ticket ${text.toUpperCase()} that you can see.`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="relative w-full max-w-md">
      <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
      <input
        ref={input}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={busy}
        placeholder="Search tickets or jump to TCK-2026-0001"
        className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pr-10 pl-9 text-sm placeholder:text-slate-400 focus:border-navy-600 focus:bg-white focus:ring-4 focus:ring-navy-100 focus:outline-none"
        aria-label="Search tickets or jump to a reference"
      />
      <kbd className="absolute top-1/2 right-3 hidden -translate-y-1/2 rounded border border-slate-200 bg-white px-1.5 text-[10px] text-slate-400 sm:block">/</kbd>
    </form>
  );
}
