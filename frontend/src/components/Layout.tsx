import { NavLink, Outlet } from "react-router";
import { useAuth } from "../auth/auth-context";

function navClass({ isActive }: { isActive: boolean }): string {
  return isActive
    ? "font-semibold text-blue-700"
    : "text-slate-600 hover:text-slate-900";
}

export default function Layout() {
  const { user, logout } = useAuth();

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
        </nav>
        <span className="flex-1" />
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