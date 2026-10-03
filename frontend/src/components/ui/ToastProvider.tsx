import { useCallback, useState, type ReactNode } from "react";
import { Icon } from "./Icon";
import { ToastContext, type ToastTone } from "./toast-context";

type Toast = { id: number; message: string; tone: ToastTone };

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);

  const show = useCallback(
    (message: string, tone: ToastTone = "success") => {
      const id = nextId++;
      setToasts((all) => [...all.slice(-3), { id, message, tone }]);
      window.setTimeout(() => dismiss(id), tone === "error" ? 6000 : 3500);
    },
    [dismiss],
  );

  return (
    <ToastContext value={show}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-full max-w-sm flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex animate-slide-up items-start gap-3 rounded-xl bg-navy-900 px-4 py-3 text-sm text-white shadow-float"
          >
            <Icon
              name={t.tone === "error" ? "alert" : t.tone === "info" ? "info" : "checkCircle"}
              className={`mt-0.5 size-4.5 shrink-0 ${t.tone === "error" ? "text-red-400" : "text-leaf-400"}`}
            />
            <p className="flex-1">{t.message}</p>
            <button type="button" onClick={() => dismiss(t.id)} className="text-white/60 hover:text-white" aria-label="Dismiss">
              <Icon name="x" className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext>
  );
}
