import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { onSessionExpired } from "../api/client";
import { getMe, login as apiLogin, logout as apiLogout } from "../api/endpoints";
import { tokens } from "../api/tokens";
import type { User } from "../api/types";
import { AuthContext, type AuthStatus, type PermissionName } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);

  const [status, setStatus] = useState<AuthStatus>(() =>
    tokens.getRefresh() ? "loading" : "signed-out",
  );

  const reset = useCallback(() => {
    tokens.clear();
    setUser(null);
    setStatus("signed-out");
    queryClient.clear();
  }, [queryClient]);

  // client.ts calls this when a refresh fails: the session is really over.
  useEffect(() => {
    onSessionExpired(reset);
  }, [reset]);

  useEffect(() => {
    if (status !== "loading") return;

    let cancelled = false;
    getMe()
      .then((me) => {
        if (!cancelled) {
          setUser(me);
          setStatus("signed-in");
        }
      })
      .catch(() => {
        if (!cancelled) reset();
      });
    return () => {
      cancelled = true;
    };
  }, [status, reset]);

  const login = useCallback(
    async (email: string, password: string) => {
      const pair = await apiLogin(email, password);
      tokens.set(pair);
      queryClient.clear();
      const me = await getMe();
      setUser(me);
      setStatus("signed-in");
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    const refresh = tokens.getRefresh();
    try {
      if (refresh) await apiLogout(refresh);
    } finally {
      reset();
    }
  }, [reset]);

  const can = useCallback(
    (permission: PermissionName) => user?.role.permissions.includes(permission) ?? false,
    [user],
  );

  const value = useMemo(
    () => ({ user, status, login, logout, can }),
    [user, status, login, logout, can],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}