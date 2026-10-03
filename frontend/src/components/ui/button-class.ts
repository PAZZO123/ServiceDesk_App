// Kept apart from Button.tsx: a file that exports components should export
// only components (React Fast Refresh rule).
export type Variant = "primary" | "accent" | "secondary" | "ghost" | "danger" | "light";
export type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-navy-900 text-white hover:bg-navy-800 shadow-sm",
  accent: "bg-leaf-500 text-navy-950 hover:bg-leaf-400 shadow-sm",
  secondary: "bg-white text-navy-900 border border-slate-300 hover:border-navy-600 hover:bg-navy-50",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-navy-900",
  danger: "bg-red-600 text-white hover:bg-red-700 shadow-sm",
  light: "bg-white/10 text-white border border-white/20 hover:bg-white/20",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra = ""): string {
  return [
    "inline-flex items-center justify-center rounded-lg font-medium transition-colors",
    "disabled:pointer-events-none disabled:opacity-55",
    VARIANTS[variant],
    SIZES[size],
    extra,
  ].join(" ");
}
