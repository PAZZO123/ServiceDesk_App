import type { ReactNode } from "react";
import { Link } from "react-router";
import { Icon } from "../components/ui/Icon";
import { Logo } from "../components/ui/Logo";

type Props = { title: string; subtitle?: ReactNode; children: ReactNode };

const POINTS = [
  "Every ticket routed to the right team the moment it is raised",
  "SLA deadlines tracked to the minute, breaches flagged automatically",
  "Live updates: no refresh button, ever",
];

// Split screen used by sign in, sign up and the password pages:
// brand panel on the left, the form on the right.
export function AuthLayout({ title, subtitle, children }: Props) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <title>{`${title} | ServiceDesk`}</title>

      {/* Left: brand panel (desktop only) */}
      <aside className="relative hidden overflow-hidden bg-navy-900 lg:block">
        <div className="absolute -top-32 -left-24 size-96 rounded-full bg-leaf-500/20 blur-3xl" />
        <div className="absolute -right-20 -bottom-40 size-[28rem] rounded-full bg-navy-600/40 blur-3xl" />
        <div className="relative flex h-full flex-col px-14 py-8 xl:px-20">
          <Link to="/" className="w-fit">
            <Logo light />
          </Link>
          <div className="flex flex-1 flex-col justify-center py-10">
            <span className="chip w-fit bg-white/10 text-leaf-400">
              <Icon name="zap" className="size-3.5" />
              Built for support teams
            </span>
            <h2 className="mt-6 max-w-md text-4xl leading-tight font-semibold text-white">
              Resolve faster. Prove it with <span className="text-leaf-500">data</span>.
            </h2>
            <ul className="mt-10 space-y-5">
              {POINTS.map((point) => (
                <li key={point} className="flex items-start gap-3 text-white/80">
                  <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-leaf-500/20 text-leaf-400">
                    <Icon name="check" className="size-3.5" strokeWidth={2.5} />
                  </span>
                  {point}
                </li>
              ))}
            </ul>
            <div className="mt-14 grid max-w-md grid-cols-3 gap-4 rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">
              {[
                ["4", "roles"],
                ["24/7", "live sync"],
                ["100%", "audited"],
              ].map(([value, label]) => (
                <div key={label}>
                  <p className="text-2xl font-semibold text-white">{value}</p>
                  <p className="text-xs text-white/60">{label}</p>
                </div>
              ))}
            </div>
          </div>
          <p className="text-xs text-white/40">© {new Date().getFullYear()} ServiceDesk. Internal IT support platform.</p>
        </div>
      </aside>

      {/* Right: the form */}
      <div className="flex flex-col bg-white px-6 py-8 sm:px-12">
        {/* On phones the brand panel is hidden, so the logo sits here. */}
        <Link to="/" className="w-fit lg:hidden">
          <Logo />
        </Link>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <h1 className="text-2xl font-semibold text-navy-900 sm:text-3xl">{title}</h1>
          {subtitle && <p className="mt-2 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8 animate-fade-in">{children}</div>
        </div>
        <p className="text-xs text-slate-400 lg:hidden">© {new Date().getFullYear()} ServiceDesk. Internal IT support platform.</p>
      </div>
    </div>
  );
}
