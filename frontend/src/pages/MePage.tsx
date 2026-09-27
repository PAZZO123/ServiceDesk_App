import { useAuth } from "../auth/auth-context";

export default function MePage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <section className="card space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{user.full_name}</h2>
        <p className="text-sm text-slate-500">{user.email}</p>
      </div>

      <p className="text-sm">
        Role: <span className="badge">{user.role.name}</span>
      </p>

      <div>
        <h3 className="mb-2 text-sm font-semibold">What this role allows</h3>
        {user.role.permissions.length === 0 ? (
          <p className="text-sm text-slate-500">
            No special permissions: you can raise tickets and follow your own.
          </p>
        ) : (
          // Tailwind resets list styles, so bullets must be switched back on.
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {user.role.permissions.map((permission) => (
              <li key={permission}>
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{permission}</code>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-slate-500">Timezone: {user.timezone}</p>
    </section>
  );
}