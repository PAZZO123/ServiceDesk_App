import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function Spinner({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`animate-spin ${className}`} aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" fill="none" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" fill="none" />
    </svg>
  );
}

export function PageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-slate-500">
      <Spinner className="size-7 text-navy-700" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-slate-200/70 ${className}`} />;
}

type EmptyProps = {
  icon?: IconName;
  title: string;
  text?: string;
  action?: ReactNode;
};

export function EmptyState({ icon = "inbox", title, text, action }: EmptyProps) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="mb-4 grid size-14 place-items-center rounded-2xl bg-navy-50 text-navy-700">
        <Icon name={icon} className="size-7" />
      </span>
      <h3 className="text-base font-semibold text-navy-900">{title}</h3>
      {text && <p className="mt-1 max-w-sm text-sm text-slate-500">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

type AlertTone = "error" | "success" | "info" | "warning";

const TONES: Record<AlertTone, { box: string; icon: IconName }> = {
  error: { box: "border-red-200 bg-red-50 text-red-800", icon: "alert" },
  success: { box: "border-leaf-400/50 bg-leaf-50 text-leaf-700", icon: "checkCircle" },
  info: { box: "border-navy-100 bg-navy-50 text-navy-800", icon: "info" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-800", icon: "alert" },
};

export function Alert({ tone = "error", children }: { tone?: AlertTone; children: ReactNode }) {
  const { box, icon } = TONES[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex gap-2.5 rounded-lg border px-3.5 py-3 text-sm ${box}`}>
      <Icon name={icon} className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
