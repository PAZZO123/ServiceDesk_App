import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth, type PermissionName } from "../auth/auth-context";
import { EmptyState, PageLoader } from "./ui/Feedback";

// Signed out -> /login, remembering where the user wanted to go.
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, signedOutByUser } = useAuth();
  const location = useLocation();

  if (status === "loading") return <PageLoader label="Restoring your session" />;
  if (status === "signed-out") {
    if (signedOutByUser) return <Navigate to="/login" replace />;
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

// Page-level guard. Hiding the menu link is not security (the API checks
// every call); this only gives a clear message instead of failing calls.
export function RequirePermission({ any, children }: { any: PermissionName[]; children: ReactNode }) {
  const { can } = useAuth();
  if (!any.some((p) => can(p))) {
    return (
      <div className="card">
        <EmptyState icon="lock" title="You do not have access to this page" text="Ask an administrator if you think you should." />
      </div>
    );
  }
  return <>{children}</>;
}
