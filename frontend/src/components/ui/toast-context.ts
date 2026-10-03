import { createContext, useContext } from "react";

export type ToastTone = "success" | "error" | "info";
export type ToastFn = (message: string, tone?: ToastTone) => void;

export const ToastContext = createContext<ToastFn | null>(null);

// const toast = useToast(); toast("Saved"); toast("Failed", "error");
export function useToast(): ToastFn {
  const value = useContext(ToastContext);
  if (value === null) throw new Error("useToast must be used inside <ToastProvider>.");
  return value;
}
