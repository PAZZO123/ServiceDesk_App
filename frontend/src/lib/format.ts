// Formatting helpers shared by every page.

const dateTime = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const dateOnly = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "Not yet";
}

export function formatDay(iso: string | null | undefined): string {
  return iso ? dateOnly.format(new Date(iso)) : "";
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

// "3 hours ago", "in 2 days". Falls back to "just now" under a minute.
export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const seconds = (new Date(iso).getTime() - now) / 1000;
  for (const [unit, size] of STEPS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "No data";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return Number.isInteger(hours) ? `${hours} h` : `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} days`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

// "ticket.view_all" -> "Ticket view all"; "in_progress" -> "In progress".
export function humanize(value: string): string {
  const text = value.replace(/[._]/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function plural(count: number, word: string, many = `${word}s`): string {
  return `${count} ${count === 1 ? word : many}`;
}
