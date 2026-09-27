import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth/auth-context";

export default function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <p className="grid min-h-[60vh] place-items-center text-slate-500">Checking your session…</p>;
  }

  if (status === "signed-out") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}