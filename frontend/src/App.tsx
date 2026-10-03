import { Route, Routes } from "react-router";
import { Perm } from "./auth/auth-context";
import { RequireAuth, RequirePermission } from "./components/RequireAuth";
import { AppLayout } from "./layouts/AppLayout";
import { ActivityPage } from "./pages/app/ActivityPage";
import { AnalyticsPage } from "./pages/app/AnalyticsPage";
import { DashboardPage } from "./pages/app/DashboardPage";
import { NewTicketPage } from "./pages/app/NewTicketPage";
import { NotificationsPage } from "./pages/app/NotificationsPage";
import { RolesPage } from "./pages/app/RolesPage";
import { SettingsPage } from "./pages/app/SettingsPage";
import { TeamsPage } from "./pages/app/TeamsPage";
import { TicketDetailPage } from "./pages/app/TicketDetailPage";
import { TicketsPage } from "./pages/app/TicketsPage";
import { UsersPage } from "./pages/app/UsersPage";
import {
  ForgotPasswordPage,
  LoginPage,
  NotFoundPage,
  RegisterPage,
  ResendVerificationPage,
  ResetPasswordPage,
  VerifyEmailPage,
} from "./pages/public/AuthPages";
import { LandingPage } from "./pages/public/LandingPage";

export default function App() {
  return (
    <Routes>
      {/* Public. /verify-email and /reset-password are the links inside
          the emails (app/core/email.py), so these paths must not change. */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/resend-verification" element={<ResendVerificationPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Signed in */}
      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="tickets" element={<TicketsPage />} />
        <Route path="tickets/new" element={<NewTicketPage />} />
        <Route path="tickets/:id" element={<TicketDetailPage />} />
        <Route path="activity" element={<ActivityPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="teams" element={<TeamsPage />} />
        <Route
          path="analytics"
          element={
            <RequirePermission any={[Perm.VIEW_ALL]}>
              <AnalyticsPage />
            </RequirePermission>
          }
        />
        <Route
          path="users"
          element={
            <RequirePermission any={[Perm.USER_MANAGE]}>
              <UsersPage />
            </RequirePermission>
          }
        />
        <Route
          path="roles"
          element={
            <RequirePermission any={[Perm.USER_MANAGE, Perm.ROLE_MANAGE]}>
              <RolesPage />
            </RequirePermission>
          }
        />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
