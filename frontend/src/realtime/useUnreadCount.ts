import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, apiRaw, ensureFreshToken } from "../api/client";
import type { UnreadCount } from "../api/types";
import { createSseParser } from "./sse"; // the file from the last message

// ── Helper 1: sleep ──────────────────────────────────────────
// Waits `ms` milliseconds, but wakes up at once if `signal` is aborted.
// Why not a plain setTimeout? When the user logs out, the component
// disappears. A plain sleep would keep running for up to 30 seconds and
// then try to reconnect. With the signal we stop immediately.
function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer); // cancel the waiting
        resolve(); // and let the caller continue
      },
      { once: true }, // run this listener only one time
    );
  });
}

// ── Helper 2: open the stream ONCE and read it until it ends ──
// Returns true if at least one count arrived (the caller uses this to
// reset its waiting time). It throws if the request fails.
async function readStreamOnce(
  signal: AbortSignal,
  onUnread: (count: number) => void,
): Promise<boolean> {
  // We use apiRaw, not api, because api() would wait for the whole body
  // as JSON. A stream never ends, so we want the raw Response object.
  // apiRaw also adds the Authorization header and, on a 401, refreshes
  // the token and retries once. EventSource could not do either.
  // `signal` lets us cancel the request from outside.
  const res = await apiRaw("/notifications/stream", {
    signal,
    headers: { Accept: "text/event-stream" },
  });
  if (res.body === null) return false;

  // res.body is a ReadableStream of bytes. getReader() lets us read
  // it piece by piece as the pieces arrive.
  const reader = res.body.getReader();
  const decoder = new TextDecoder(); // bytes -> text
  const parse = createSseParser(); // text -> events
  let gotData = false;

  // We stop with `break` when the server ends the stream. It does that
  // when the access token expires (see stream_unread_count in Python).
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // { stream: true } = "more bytes may follow". It keeps a
    // half-received character (like "é", 2 bytes) for the next chunk.
    const text = decoder.decode(value, { stream: true });

    for (const message of parse(text)) {
      // The server sends event="unread". Ignore any other name.
      if (message.event !== "unread") continue;
      // message.data is a JSON string like '{"unread":3}'.
      // The `as UnreadCount` says: "trust me, this is the shape".
      // TypeScript cannot check data that comes from the network.
      const parsed = JSON.parse(message.data) as UnreadCount;
      onUnread(parsed.unread);
      gotData = true;
    }
  }
  return gotData;
}

// ── The hook ─────────────────────────────────────────────────
// Returns the unread count, or null until the first count arrives.
// null is not the same as 0. The Layout can show nothing while we don't
// know, instead of a wrong "0" that then jumps to "5".
export function useUnreadCount(): number | null {
  const [unread, setUnread] = useState<number | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    // One AbortController per effect run. Calling controller.abort() in
    // the cleanup (bottom) cancels the fetch AND wakes up sleep().
    const controller = new AbortController();
    const { signal } = controller;

    async function run(): Promise<void> {
      let delay = 1_000; // waiting time after a failure, in ms

      while (!signal.aborted) {
        try {
          const gotData = await readStreamOnce(signal, (count) => {
            setUnread(count);
            // The count changed, so the list page may be out of date.
            // Marking ["notifications"] as stale makes any open list
            // refetch. (The first count on connect also does this.
            // That is one extra request, which is fine.)
            void queryClient.invalidateQueries({ queryKey: ["notifications"] });
          });

          if (gotData) delay = 1_000; // it worked, so forget old failures

          // If we are here, the stream ended normally: the server closed it
          // because the access token expired. Get a fresh token BEFORE we
          // reconnect. Without this, the new request would use the old
          // token, get a 401, and refresh anyway. This is the same idea as
          // ensureFreshToken() in useLiveUpdates.ts.
          // false = the refresh failed. client.ts already called the
          // session-expired handler (the user goes to the login page),
          // so we stop.
          if (!(await ensureFreshToken())) return;
        } catch (err) {
          // Aborting makes fetch throw an AbortError. That is not a failure.
          if (signal.aborted) return;
          // 401/403 that survived apiRaw's own refresh-and-retry means the
          // session is over. Retrying would only hammer the server.
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return;
          // Anything else (network down, server restarting): fall through,
          // wait, and try again.
        }

        await sleep(delay, signal);
        // Wait longer after each failure: 1s, 2s, 4s ... up to 30s.
        // Math.min stops the growth at 30 seconds.
        delay = Math.min(delay * 2, 30_000);
      }
    }

    // `void` = "I know this is a promise and I am not waiting for it".
    // The ESLint rule no-floating-promises wants this to be explicit.
    void run();

    // React calls this when the component unmounts (logout), and also
    // in dev StrictMode (mount, unmount, mount again). Cleaning up
    // properly is what makes StrictMode harmless here.
    return () => controller.abort();
  }, [queryClient]);

  return unread;
}