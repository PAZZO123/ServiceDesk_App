// Tiny dependency-free charts drawn with CSS and SVG.

export type Slice = { label: string; value: number; color: string };

// A ring chart. Each slice is one stroked circle with a dash offset.
export function Donut({ slices, centerLabel, centerValue }: { slices: Slice[]; centerLabel: string; centerValue: string | number }) {
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  const radius = 15.915; // circumference = 100, so a dash length is a percentage
  let offset = 25; // start at 12 o'clock
  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row">
      <div className="relative size-40 shrink-0">
        <svg viewBox="0 0 42 42" className="size-full">
          <circle cx="21" cy="21" r={radius} fill="none" stroke="#e6ecf5" strokeWidth="5" />
          {total > 0 &&
            slices.map((s) => {
              const pct = (s.value / total) * 100;
              const el = (
                <circle
                  key={s.label}
                  cx="21"
                  cy="21"
                  r={radius}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="5"
                  strokeDasharray={`${pct} ${100 - pct}`}
                  strokeDashoffset={offset}
                />
              );
              offset -= pct;
              return el;
            })}
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <p className="text-2xl font-semibold text-navy-900">{centerValue}</p>
            <p className="text-xs text-slate-500">{centerLabel}</p>
          </div>
        </div>
      </div>
      <ul className="w-full space-y-2.5">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-3 text-sm">
            <span className="size-2.5 rounded-full" style={{ backgroundColor: s.color }} />
            <span className="flex-1 text-slate-600">{s.label}</span>
            <span className="font-semibold text-navy-900">{s.value}</span>
            <span className="w-10 text-right text-xs text-slate-400">{total ? Math.round((s.value / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export type Bar = { label: string; value: number | null; note?: string };

// Horizontal bars. `max` fixes the scale (100 for percentages).
export function BarList({ bars, max, unit = "", good }: { bars: Bar[]; max?: number; unit?: string; good?: (v: number) => boolean }) {
  const top = max ?? Math.max(1, ...bars.map((b) => b.value ?? 0));
  return (
    <ul className="space-y-4">
      {bars.map((b) => {
        const pct = b.value === null ? 0 : Math.min(100, (b.value / top) * 100);
        const color = b.value === null ? "bg-slate-200" : good && !good(b.value) ? "bg-amber-400" : "bg-leaf-500";
        return (
          <li key={b.label}>
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700">{b.label}</span>
              <span className="text-slate-500">
                {b.value === null ? "No data" : `${b.value}${unit}`}
                {b.note && <span className="ml-2 text-xs text-slate-400">{b.note}</span>}
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-navy-50">
              <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
