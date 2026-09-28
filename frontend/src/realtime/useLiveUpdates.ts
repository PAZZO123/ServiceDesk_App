import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ensureFreshToken } from "../api/client";
import { tokens } from "../api/tokens";

export type LiveStatus = "connecting" | "live" | "offline";

// What app/api/v1/realtime.py can send us.
type ServerMessage =
  | { type: "ready" }
  | { type: "resync" }
  | { type: "ticket"; kind: string; ticket_id: string };

const CLOSE_UNAUTHORIZED = 4401;
const MAX_DELAY_MS = 30_000;

function socketUrl(): string {
  // Same host as the page. In development, Vite forwards it (ws: true).
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/api/v1/ws`;
}

export function useLiveUpdates(): LiveStatus {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>("connecting");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let attempt = 0;
    let stopped = false;

    function retryLater() {
      // Wait longer after every failure - 1s, 2s, 4s ... 30s - so a server
      // that is down is not hammered by every open tab.
      const delay = Math.min(1000 * 2 ** attempt, MAX_DELAY_MS);
      attempt += 1;
      timer = window.setTimeout(connect, delay);
    }

    function connect() {
      const ws = new WebSocket(socketUrl());
      socket = ws;

      // The first message proves who we are (see realtime.py for why).
      ws.onopen = () => ws.send(JSON.stringify({ type: "auth", token: tokens.getAccess() }));

      ws.onmessage = (event: MessageEvent<string>) => {
        const message = JSON.parse(event.data) as ServerMessage;
        if (message.type === "ready") {
          // After a reconnect we may have missed events: reload everything.
          if (attempt > 0) void queryClient.invalidateQueries();
          attempt = 0;
          setStatus("live");
        } else if (message.type === "resync") {
          void queryClient.invalidateQueries();
        } else {
          // A doorbell, not the data: refetch through the normal API, whose
          // permission checks decide what we are allowed to see.
          void queryClient.invalidateQueries({ queryKey: ["tickets"] });
        }
      };

      ws.onclose = (event) => {
        if (stopped) return;
        setStatus("offline");
        if (event.code === CLOSE_UNAUTHORIZED) {
          // Usually just an expired access token. If the refresh fails too,
          // ensureFreshToken signs us out and this component goes away.
          void ensureFreshToken().then((ok) => {
            if (ok && !stopped) retryLater();
          });
          return;
        }
        retryLater();
      };
    }

    connect();

    // Runs on sign-out, and in development when StrictMode mounts twice.
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      socket?.close();
    };
  }, [queryClient]);

  return status;
}