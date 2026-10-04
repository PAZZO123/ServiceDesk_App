import { createContext, useContext } from "react";
import type { User } from "../api/types";

// Hand-copied from app/models/enums.py (Permission). The UI only uses these
// to hide buttons; the server checks every request again.
export const Perm = {
  VIEW_ALL: "ticket.view_all",
  WORK: "ticket.work",
  DELETE: "ticket.delete",
  STARTS_HIGH: "ticket.starts_high",
  READ_INTERNAL: "comment.read_internal",
  MODERATE: "content.moderate",
  TEAM_MANAGE: "team.manage",
  USER_MANAGE: "user.manage",
  ROLE_MANAGE: "role.manage",
  REASSIGN: "ticket.reassign",
} as const;

export type PermissionName = (typeof Perm)[keyof typeof Perm];
export type AuthStatus = "loading" | "signed-in" | "signed-out";

export type AuthValue = {
  user: User | null;
  status: AuthStatus;
  // True after the user pressed "Sign out" (not after an expired session):
  // the login page then opens without "?next=" to the previous user's page.
  signedOutByUser: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  // Replace the cached user after PATCH /auth/me or /auth/me/profile.
  setUser: (user: User) => void;
  can: (permission: PermissionName) => boolean;
};

export const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return value;
}
