import type { TokenPair } from "./types";

const REFRESH_KEY = "servicedesk.refresh";

let accessToken: string | null = null;
export const tokens = {
  getAccess(): string | null {
    return accessToken;
  },

  getRefresh(): string | null {
    try {
      return localStorage.getItem(REFRESH_KEY);
    } catch {
      return null;
    }
  },

  set(pair: TokenPair): void {
    accessToken = pair.access_token;
    try {
      localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    } catch {
      // works for this tab, just won't survive a reload
    }
  },

  clear(): void {
    accessToken = null;
    try {
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      // nothing to do
    }
  },
};