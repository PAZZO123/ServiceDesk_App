export function LogoMark({ className = "size-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#041738" />
      <path d="M9 17.5l4.2 4.2L23 11.9" fill="none" stroke="#89C550" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark />
      <span className={`text-lg font-semibold tracking-tight ${light ? "text-white" : "text-navy-900"}`}>
        Service<span className="text-leaf-500">Desk</span>
      </span>
    </span>
  );
}
