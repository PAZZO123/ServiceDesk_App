import { NavLink, Outlet } from "react-router";
import { useAuth } from "../auth/auth-context";
import { useLiveUpdates, type LiveStatus } from "../realtime/useLiveUpdates";
import { useUnreadCount } from "../realtime/useUnreadCount";

function navClass({ isActive }: { isActive: boolean }): string {
  return isActive
    ? "font-semibold text-blue-700"
    : "text-slate-600 hover:text-slate-900";
}


const LIVE_DOT: Record<LiveStatus, string> = {
  connecting: "bg-amber-400",
  live: "bg-green-500",
  offline: "bg-red-500",
};

export default function Layout() {
const unread = useUnreadCount(); // number | null
  const { user, logout } = useAuth();
  // Layout is only shown when signed in, so this is the right place to hold
  // the live connection: it opens at sign-in and closes at sign-out.
  const live = useLiveUpdates();

  return (
    <div className="min-h-screen">
      <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-5 py-2.5">
        <strong>ServiceDesk</strong>
        <nav className="flex gap-4 text-sm">
          <NavLink to="/tickets" end className={navClass}>
            Tickets
          </NavLink>
          <NavLink to="/tickets/new" className={navClass}>
            New ticket
          </NavLink>
          <NavLink to="/me" className={navClass}>
            My account
          </NavLink>
          <NavLink to="/notifications" /* same className as your other links */>
  Notifications
 
  {!!unread && (
    <span className="ml-1 rounded-full bg-red-600 px-1.5 text-xs text-white">
      {unread}
    </span>
  )}
</NavLink>
        </nav>
        <span className="flex-1" />
        <span className="flex items-center gap-1.5 text-xs text-slate-500" title="Live updates">
          <span className={`size-2 rounded-full ${LIVE_DOT[live]}`} />
          {live}
        </span>
        <span className="text-sm text-slate-500">
          {user?.full_name} · {user?.role.name}
        </span>
        <button className="btn-secondary" onClick={() => void logout()}>
          Sign out
        </button>
      </header>
      <main className="mx-auto my-6 max-w-5xl px-4">
        <Outlet />
      </main>
    </div>
  );
}