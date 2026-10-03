import { useState } from "react";
import { Link } from "react-router";
import { useAuth } from "../../auth/auth-context";
import { ButtonLink } from "../../components/ui/Button";
import { Icon, type IconName } from "../../components/ui/Icon";
import { Logo } from "../../components/ui/Logo";

const NAV_LINKS = [
  ["Features", "#features"],
  ["How it works", "#how"],
  ["Roles", "#roles"],
  ["Security", "#security"],
] as const;

const FEATURES: { icon: IconName; title: string; text: string }[] = [
  { icon: "layers", title: "Automatic routing", text: "Pick a category and the ticket lands in the right team's queue with its SLA deadline already set." },
  { icon: "clock", title: "SLA tracking", text: "Every ticket carries a deadline. A background sweep flags breaches every minute and alerts the owner." },
  { icon: "zap", title: "Live updates", text: "Lists, ticket pages and the notification badge refresh themselves the moment something changes." },
  { icon: "lock", title: "Internal notes", text: "Agents discuss a ticket privately. Requesters never see a note, a count or even a hint that it exists." },
  { icon: "paperclip", title: "Safe attachments", text: "Files are checked by their real content, stored under random names and only served after a permission check." },
  { icon: "search", title: "Full-text search", text: "Search like you search the web: phrases, OR, and minus to exclude. Results ranked by relevance." },
  { icon: "chart", title: "Team analytics", text: "SLA performance, median resolution time and workload share per team, ranked for managers." },
  { icon: "shield", title: "Roles you control", text: "Create roles and grant permissions from the app. Every change is written to the audit log." },
];

const STEPS = [
  { n: "01", title: "Raise", text: "A requester describes the problem and picks a category. Nothing else to fill in." },
  { n: "02", title: "Route and work", text: "The right team is notified, an agent claims it and keeps the requester posted with comments." },
  { n: "03", title: "Resolve and measure", text: "The fix is confirmed, the ticket closes, and every minute of it shows up in the analytics." },
];

const ROLES: { icon: IconName; name: string; tagline: string; can: string[] }[] = [
  { icon: "user", name: "Requester", tagline: "Anyone who needs help", can: ["Raise and follow tickets", "Comment and attach files", "Close their own ticket"] },
  { icon: "ticket", name: "Agent", tagline: "Support staff", can: ["Work their team's queue", "Claim, assign and tag", "Write internal notes"] },
  { icon: "eye", name: "Observer", tagline: "Managers and leadership", can: ["See every ticket", "Read internal notes", "Open the analytics"] },
  { icon: "shield", name: "Admin", tagline: "Runs the platform", can: ["Manage users and teams", "Create roles and permissions", "Moderate content"] },
];

const SECURITY = [
  "Refresh tokens rotate on every use; a reused token ends the whole session family",
  "Logging out or changing a password signs you out on every device",
  "Lists and single tickets use the same permission rules, tested on every commit",
  "Login, sign up and password reset are rate limited against guessing",
  "Every change to a ticket, team or role is written to an audit log",
];

export function LandingPage() {
  const { status } = useAuth();
  const [menu, setMenu] = useState(false);
  const signedIn = status === "signed-in";

  return (
    <div className="bg-white">
      {/* Navigation */}
      <header className="sticky top-0 z-30 border-b border-slate-100 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-8 md:flex">
            {NAV_LINKS.map(([label, href]) => (
              <a key={href} href={href} className="text-sm text-slate-600 transition hover:text-navy-900">
                {label}
              </a>
            ))}
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            {signedIn ? (
              <ButtonLink to="/app" iconRight="arrowRight">
                Open dashboard
              </ButtonLink>
            ) : (
              <>
                <Link to="/login" className="text-sm font-medium text-navy-900 hover:text-navy-700">
                  Sign in
                </Link>
                <ButtonLink to="/register">Get started</ButtonLink>
              </>
            )}
          </div>
          <button type="button" className="rounded-lg p-2 text-slate-700 md:hidden" onClick={() => setMenu((m) => !m)} aria-label="Menu">
            <Icon name={menu ? "x" : "menu"} />
          </button>
        </div>
        {menu && (
          <div className="border-t border-slate-100 px-4 py-4 md:hidden">
            <div className="flex flex-col gap-3">
              {NAV_LINKS.map(([label, href]) => (
                <a key={href} href={href} onClick={() => setMenu(false)} className="text-sm text-slate-700">
                  {label}
                </a>
              ))}
              <div className="mt-2 grid grid-cols-2 gap-3">
                {signedIn ? (
                  <ButtonLink to="/app" className="col-span-2">
                    Open dashboard
                  </ButtonLink>
                ) : (
                  <>
                    <ButtonLink to="/login" variant="secondary">
                      Sign in
                    </ButtonLink>
                    <ButtonLink to="/register">Get started</ButtonLink>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 -z-0 h-[36rem] bg-linear-to-b from-navy-50 to-white" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-4 pt-16 pb-20 sm:px-6 lg:grid-cols-[1fr_1.15fr] lg:px-8 lg:pt-24">
          <div className="animate-slide-up">
            <span className="chip bg-leaf-100 text-leaf-700">
              <Icon name="sparkle" className="size-3.5" />
              IT support platform
            </span>
            <h1 className="mt-6 text-4xl leading-[1.1] font-bold tracking-tight text-navy-900 sm:text-5xl xl:text-6xl">
              IT support that runs <span className="text-leaf-500">on time</span>.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">
              ServiceDesk brings every request, every team and every deadline into one calm workspace. Tickets route
              themselves, SLAs watch the clock, and managers see exactly how support is performing.
            </p>
            <p className="mt-5 text-base font-semibold text-navy-900">
              Fast. Clear. <span className="text-leaf-500">Accountable.</span>
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink to={signedIn ? "/app" : "/register"} size="lg" iconRight="arrowRight">
                {signedIn ? "Open dashboard" : "Get started free"}
              </ButtonLink>
              {!signedIn && (
                <ButtonLink to="/login" size="lg" variant="secondary" className="border-leaf-500 text-leaf-700 hover:border-leaf-600 hover:bg-leaf-50">
                  Sign in
                </ButtonLink>
              )}
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
              {["No setup required", "Works on any device", "Secure by design"].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <Icon name="checkCircle" className="size-4 text-leaf-500" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <HeroPreview />
        </div>
      </section>

      {/* Stats strip */}
      <section className="border-y border-slate-100 bg-navy-50/50">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-4 py-10 sm:px-6 md:grid-cols-4 lg:px-8">
          {[
            ["Under 1 s", "from change to every open screen"],
            ["Every minute", "SLA deadlines checked"],
            ["4 roles", "9 fine grained permissions"],
            ["116 tests", "run on every commit"],
          ].map(([value, label]) => (
            <div key={label}>
              <p className="text-2xl font-semibold text-navy-900">{value}</p>
              <p className="mt-1 text-sm text-slate-500">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-24 sm:px-6 lg:px-8">
        <SectionTitle eyebrow="Features" title="Everything a support desk needs, nothing it does not" text="Designed around how IT teams actually work: a clear queue, honest deadlines and fewer status meetings." />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="group rounded-2xl border border-slate-200 p-6 transition hover:-translate-y-0.5 hover:border-navy-100 hover:shadow-card">
              <span className="grid size-11 place-items-center rounded-xl bg-navy-900 text-leaf-400 transition group-hover:bg-leaf-500 group-hover:text-navy-950">
                <Icon name={f.icon} className="size-5" />
              </span>
              <h3 className="mt-5 font-semibold text-navy-900">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 bg-navy-900 py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <SectionTitle light eyebrow="How it works" title="From problem to solved in three steps" />
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <div key={step.n} className="relative rounded-2xl border border-white/10 bg-white/5 p-7">
                <span className="text-4xl font-bold text-leaf-500/90">{step.n}</span>
                <h3 className="mt-4 text-lg font-semibold text-white">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/65">{step.text}</p>
                {i < STEPS.length - 1 && (
                  <Icon name="arrowRight" className="absolute top-1/2 -right-5 hidden size-6 -translate-y-1/2 text-white/25 md:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Roles */}
      <section id="roles" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-24 sm:px-6 lg:px-8">
        <SectionTitle eyebrow="Roles" title="The right view for every person" text="Four built-in roles cover most organisations. Need something in between? Create your own role in a minute." />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {ROLES.map((role) => (
            <div key={role.name} className="rounded-2xl border border-slate-200 bg-white p-6">
              <span className="grid size-11 place-items-center rounded-xl bg-leaf-100 text-leaf-700">
                <Icon name={role.icon} />
              </span>
              <h3 className="mt-5 text-lg font-semibold text-navy-900">{role.name}</h3>
              <p className="text-sm text-slate-500">{role.tagline}</p>
              <ul className="mt-5 space-y-2.5">
                {role.can.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm text-slate-700">
                    <Icon name="check" className="mt-0.5 size-4 shrink-0 text-leaf-500" strokeWidth={2.4} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Security */}
      <section id="security" className="scroll-mt-20 bg-navy-50/60 py-24">
        <div className="mx-auto grid max-w-7xl items-center gap-14 px-4 sm:px-6 lg:grid-cols-2 lg:px-8">
          <div>
            <SectionTitle align="left" eyebrow="Security" title="Secure by default, not by checklist" text="Support tickets hold password reset requests, salary questions and screenshots. ServiceDesk treats them that way." />
            <ul className="mt-8 space-y-4">
              {SECURITY.map((item) => (
                <li key={item} className="flex items-start gap-3 text-slate-700">
                  <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-navy-900 text-leaf-400">
                    <Icon name="check" className="size-3.5" strokeWidth={2.6} />
                  </span>
                  <span className="text-sm leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl bg-navy-900 p-6 shadow-float sm:p-8">
            <div className="flex items-center gap-2">
              <span className="size-3 rounded-full bg-red-400/80" />
              <span className="size-3 rounded-full bg-amber-400/80" />
              <span className="size-3 rounded-full bg-leaf-500/80" />
              <span className="ml-3 text-xs text-white/40">audit_logs</span>
            </div>
            <div className="mt-6 space-y-3 font-mono text-xs sm:text-sm">
              {[
                ["09:14", "role_permissions_changed", "added ticket.delete"],
                ["09:22", "assigned", "TCK-2026-0042 to Amina K."],
                ["09:31", "status_changed", "in_progress to resolved"],
                ["09:40", "sla_breached", "TCK-2026-0039 flagged"],
                ["09:41", "attachment_removed", "invoice.pdf"],
              ].map(([time, action, detail]) => (
                <div key={time} className="flex flex-wrap gap-x-3 rounded-lg bg-white/5 px-3 py-2.5">
                  <span className="text-white/40">{time}</span>
                  <span className="text-leaf-400">{action}</span>
                  <span className="text-white/70">{detail}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Call to action */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-3xl bg-navy-900 px-6 py-14 text-center sm:px-14">
          <div className="absolute -top-24 -right-16 size-72 rounded-full bg-leaf-500/25 blur-3xl" />
          <div className="absolute -bottom-24 -left-16 size-72 rounded-full bg-navy-600/50 blur-3xl" />
          <div className="relative">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Ready for a calmer support queue?</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/70">Create your account in under a minute and raise your first ticket today.</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <ButtonLink to={signedIn ? "/app" : "/register"} size="lg" variant="accent" iconRight="arrowRight">
                {signedIn ? "Open dashboard" : "Create your account"}
              </ButtonLink>
              {!signedIn && (
                <ButtonLink to="/login" size="lg" variant="light">
                  I already have one
                </ButtonLink>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-100">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:px-6 lg:px-8">
          <Logo />
          <p>© {new Date().getFullYear()} ServiceDesk. Internal IT support platform.</p>
          <div className="flex gap-6">
            <a href="#features" className="hover:text-navy-900">Features</a>
            <a href="#security" className="hover:text-navy-900">Security</a>
            <Link to="/login" className="hover:text-navy-900">Sign in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function SectionTitle({
  eyebrow,
  title,
  text,
  light = false,
  align = "center",
}: {
  eyebrow: string;
  title: string;
  text?: string;
  light?: boolean;
  align?: "center" | "left";
}) {
  return (
    <div className={align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-xl"}>
      <p className="text-sm font-semibold tracking-wider text-leaf-600 uppercase">{eyebrow}</p>
      <h2 className={`mt-3 text-3xl font-semibold tracking-tight sm:text-4xl ${light ? "text-white" : "text-navy-900"}`}>{title}</h2>
      {text && <p className={`mt-4 leading-relaxed ${light ? "text-white/65" : "text-slate-500"}`}>{text}</p>}
    </div>
  );
}

// A static picture of the product, drawn with HTML so it stays sharp.
function HeroPreview() {
  const rows = [
    ["TCK-2026-0042", "VPN keeps dropping", "In progress", "bg-indigo-50 text-indigo-700", "2 h left"],
    ["TCK-2026-0041", "New laptop for Amina", "Open", "bg-sky-50 text-sky-700", "1 day left"],
    ["TCK-2026-0039", "Printer offline, floor 2", "Waiting", "bg-amber-50 text-amber-700", "Breached"],
    ["TCK-2026-0037", "Password reset", "Resolved", "bg-leaf-50 text-leaf-700", "Done"],
  ];
  const bars = [62, 80, 45, 92, 70, 88, 96];
  return (
    <div className="relative animate-fade-in lg:pl-6">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-float">
        <div className="flex">
          <div className="hidden w-36 shrink-0 bg-navy-900 p-4 sm:block">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-md bg-navy-700">
                <Icon name="check" className="size-3.5 text-leaf-400" strokeWidth={3} />
              </span>
              <span className="text-xs font-semibold text-white">ServiceDesk</span>
            </div>
            <div className="mt-4 rounded-md bg-leaf-500 py-1.5 text-center text-[10px] font-semibold text-navy-950">New ticket</div>
            <div className="mt-4 space-y-1">
              {["Dashboard", "Tickets", "Activity", "Analytics", "Teams"].map((item, i) => (
                <div key={item} className={`rounded-md px-2 py-1.5 text-[10px] ${i === 0 ? "bg-white/10 text-white" : "text-white/50"}`}>
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="min-w-0 flex-1 bg-navy-50/60 p-4">
            <p className="text-xs font-semibold text-navy-900">Good morning, Amina</p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[
                ["Open", "18", "text-navy-900"],
                ["Breached", "2", "text-red-600"],
                ["SLA met", "96%", "text-leaf-600"],
              ].map(([label, value, color]) => (
                <div key={label} className="rounded-lg bg-white p-2.5 shadow-sm">
                  <p className="text-[9px] text-slate-500">{label}</p>
                  <p className={`text-lg font-semibold ${color}`}>{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-2 grid grid-cols-5 gap-2">
              <div className="col-span-3 rounded-lg bg-white p-2.5 shadow-sm">
                <p className="text-[9px] font-medium text-slate-500">Resolved this week</p>
                <div className="mt-2 flex h-16 items-end gap-1.5">
                  {bars.map((h, i) => (
                    <span key={i} className={`flex-1 rounded-t ${i === bars.length - 1 ? "bg-leaf-500" : "bg-navy-100"}`} style={{ height: `${h}%` }} />
                  ))}
                </div>
              </div>
              <div className="col-span-2 grid place-items-center rounded-lg bg-white p-2.5 shadow-sm">
                <svg viewBox="0 0 36 36" className="size-16 -rotate-90">
                  <circle cx="18" cy="18" r="15" fill="none" stroke="#e6ecf5" strokeWidth="4" />
                  <circle cx="18" cy="18" r="15" fill="none" stroke="#89c550" strokeWidth="4" strokeDasharray="90 100" strokeLinecap="round" />
                </svg>
              </div>
            </div>
            <div className="mt-2 rounded-lg bg-white p-2 shadow-sm">
              {rows.map(([ref, title, status, style, sla]) => (
                <div key={ref} className="flex items-center gap-2 border-b border-slate-100 px-1 py-1.5 last:border-0">
                  <span className="w-20 shrink-0 font-mono text-[9px] text-slate-400">{ref}</span>
                  <span className="min-w-0 flex-1 truncate text-[10px] font-medium text-navy-900">{title}</span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[8px] font-medium ${style}`}>{status}</span>
                  <span className={`hidden w-14 text-right text-[9px] sm:block ${sla === "Breached" ? "text-red-600" : "text-slate-400"}`}>{sla}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="absolute -bottom-6 -left-2 hidden w-56 rounded-xl border border-slate-200 bg-white p-3 shadow-float sm:block">
        <div className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-lg bg-leaf-100 text-leaf-700">
            <Icon name="checkCircle" className="size-4.5" />
          </span>
          <div>
            <p className="text-xs font-semibold text-navy-900">Ticket resolved</p>
            <p className="text-[11px] text-slate-500">TCK-2026-0037 in 42 min</p>
          </div>
        </div>
      </div>
      <div className="absolute -top-5 right-2 hidden rounded-xl bg-navy-900 px-3 py-2 shadow-float sm:block">
        <p className="flex items-center gap-2 text-xs text-white">
          <span className="size-2 animate-pulse rounded-full bg-leaf-500" />
          Live: 3 agents online
        </p>
      </div>
    </div>
  );
}
