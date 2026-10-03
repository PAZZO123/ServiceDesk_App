import { useEffect, useState } from "react";

// The current time, refreshed every `everyMs`. Reading Date.now() directly
// while rendering would make the output change between renders; a value in
// state keeps rendering pure and still lets countdowns ("2 h left") move.
export function useNow(everyMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), everyMs);
    return () => window.clearInterval(timer);
  }, [everyMs]);
  return now;
}
