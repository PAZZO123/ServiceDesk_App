import { createContext, useContext } from "react";
import type { User } from "../api/types";

export const Perm = {
  VIEW_ALL: "ticket.view_all",
  WORK: "ticket.work",
  DELETE: "ticket.delete",
    STARTS_HIGH: "ticket.starts_high",
  READ_INTERNAL: "comment.read_internal",
  MODERATE: "content.moderate",
  TEAM_MANAGE: "team.manage",
  USER_MANAGE: "user.manage",
} as const;

export type PermissionName = (typeof Perm)[keyof typeof Perm];
export type AuthStatus = "loading" | "signed-in" | "signed-out";

export type AuthValue = {
  user: User | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
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