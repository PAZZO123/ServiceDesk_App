import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { ApiError } from "../../api/client";
import {
  confirmPasswordReset,
  register,
  requestPasswordReset,
  resendVerification,
  verifyEmail,
} from "../../api/endpoints";
import { useAuth } from "../../auth/auth-context";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Alert, Spinner } from "../../components/ui/Feedback";
import { TextField } from "../../components/ui/Field";
import { Icon } from "../../components/ui/Icon";
import { AuthLayout } from "../../layouts/AuthLayout";
import { errorCode, errorMessage } from "../../lib/errors";

// Only allow redirects inside the app, never to another site.
function safeNext(next: string | null): string {
  return next && next.startsWith("/app") ? next : "/app";
}

// ------------------------------------------------------------------ login

export function LoginPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get("next"));

  if (status === "signed-in") return <Navigate to={next} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const code = errorCode(error);

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your ServiceDesk workspace.">
      <form onSubmit={submit} className="space-y-5">
        {error !== null && (
          <Alert tone={code === "rate_limited" ? "warning" : "error"}>
            {code === "account_not_verified" ? (
              <>
                Please verify your email first.{" "}
                <Link to={`/resend-verification?email=${encodeURIComponent(email)}`} className="font-semibold underline">
                  Send me a new link
                </Link>
              </>
            ) : code === "invalid_credentials" ? (
              "That email and password do not match."
            ) : (
              errorMessage(error)
            )}
          </Alert>
        )}
        <TextField label="Work email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        <div>
          <TextField label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <div className="mt-2 text-right">
            <Link to="/forgot-password" className="text-sm font-medium text-navy-700 hover:text-navy-900">
              Forgot password?
            </Link>
          </div>
        </div>
        <Button type="submit" size="lg" loading={busy} className="w-full">
          Sign in
        </Button>
        <p className="text-center text-sm text-slate-500">
          New here?{" "}
          <Link to="/register" className="font-semibold text-navy-900 hover:text-navy-700">
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

// --------------------------------------------------------------- register

export function RegisterPage() {
  const { status } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [doneFor, setDoneFor] = useState<string | null>(null);

  if (status === "signed-in") return <Navigate to="/app" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(form);
      setDoneFor(form.email);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (doneFor) {
    return (
      <AuthLayout title="Check your inbox" subtitle={<>We sent a verification link to <b className="text-navy-900">{doneFor}</b>.</>}>
        <CheckEmail email={doneFor} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Create your account" subtitle="Raise and follow IT requests in one place.">
      <form onSubmit={submit} className="space-y-5">
        {error !== null && <Alert>{errorCode(error) === "user_already_exists" ? "An account with this email already exists. Try signing in." : errorMessage(error)}</Alert>}
        <TextField label="Full name" autoComplete="name" required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Amina Kayitesi" />
        <TextField label="Work email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={72}
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          hint="At least 8 characters."
        />
        <Button type="submit" size="lg" loading={busy} className="w-full">
          Create account
        </Button>
        <p className="text-center text-sm text-slate-500">
          Already registered?{" "}
          <Link to="/login" className="font-semibold text-navy-900 hover:text-navy-700">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

// "Check your email" panel with a resend button (POST /auth/resend-verification).
function CheckEmail({ email }: { email: string }) {
  const [state, setState] = useState<"idle" | "busy" | "sent" | "error">("idle");
  const [error, setError] = useState<unknown>(null);

  async function resend() {
    setState("busy");
    try {
      await resendVerification(email);
      setState("sent");
    } catch (err) {
      setError(err);
      setState("error");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-4 rounded-xl border border-slate-200 bg-navy-50/60 p-5">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-navy-900 text-leaf-400">
          <Icon name="mail" />
        </span>
        <p className="text-sm text-slate-600">Open the email and click the button inside to activate your account. The link is valid for 24 hours. Check your spam folder if it does not arrive.</p>
      </div>
      {state === "sent" && <Alert tone="success">A new link is on its way.</Alert>}
      {state === "error" && <Alert>{errorMessage(error)}</Alert>}
      <div className="flex gap-3">
        <Button variant="secondary" onClick={resend} loading={state === "busy"} disabled={state === "sent"}>
          Resend the email
        </Button>
        <ButtonLink to="/login">Go to sign in</ButtonLink>
      </div>
    </div>
  );
}

// ------------------------------------------------- resend verification

export function ResendVerificationPage() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <AuthLayout title="Check your inbox" subtitle={<>If <b className="text-navy-900">{email}</b> has an unverified account, a new link is on its way.</>}>
        <CheckEmail email={email} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Verify your email" subtitle="We will send you a fresh verification link.">
      <EmailForm email={email} setEmail={setEmail} label="Send verification link" action={resendVerification} onDone={() => setSent(true)} />
    </AuthLayout>
  );
}

// ----------------------------------------------------------- verify email

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "done" | "failed">(token ? "working" : "failed");
  const [message, setMessage] = useState("");
  const started = useRef(false);

  useEffect(() => {
    // The token is single-use: guard against StrictMode calling twice.
    if (!token || started.current) return;
    started.current = true;
    verifyEmail(token)
      .then((res) => {
        setMessage(res.message);
        setState("done");
      })
      .catch((err: unknown) => {
        setMessage(err instanceof ApiError && err.code === "already_verified" ? "Your email is already verified. You can sign in." : "This link is invalid or has expired.");
        setState(err instanceof ApiError && err.code === "already_verified" ? "done" : "failed");
      });
  }, [token]);

  return (
    <AuthLayout title={state === "working" ? "Verifying your email" : state === "done" ? "You are all set" : "Link not valid"}>
      {state === "working" && (
        <div className="flex items-center gap-3 text-slate-600">
          <Spinner className="size-5 text-navy-700" /> One moment please.
        </div>
      )}
      {state === "done" && (
        <div className="space-y-6">
          <Alert tone="success">{message || "Email verified."}</Alert>
          <ButtonLink to="/login" size="lg" className="w-full" iconRight="arrowRight">
            Sign in
          </ButtonLink>
        </div>
      )}
      {state === "failed" && (
        <div className="space-y-6">
          <Alert>{message || "This link is missing its token."}</Alert>
          <ButtonLink to="/resend-verification" variant="secondary" className="w-full">
            Send me a new link
          </ButtonLink>
        </div>
      )}
    </AuthLayout>
  );
}

// ---------------------------------------------------------- forgot password

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <AuthLayout title="Check your inbox" subtitle={<>If <b className="text-navy-900">{email}</b> has an account, a reset link is on its way. It is valid for 30 minutes.</>}>
        <ButtonLink to="/login" variant="secondary" icon="arrowLeft">
          Back to sign in
        </ButtonLink>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we will send you a link to choose a new one.">
      <EmailForm email={email} setEmail={setEmail} label="Send reset link" action={requestPasswordReset} onDone={() => setSent(true)} />
    </AuthLayout>
  );
}

function EmailForm({
  email,
  setEmail,
  label,
  action,
  onDone,
}: {
  email: string;
  setEmail: (v: string) => void;
  label: string;
  action: (email: string) => Promise<unknown>;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await action(email);
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {error !== null && <Alert tone={errorCode(error) === "rate_limited" ? "warning" : "error"}>{errorMessage(error)}</Alert>}
      <TextField label="Work email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
      <Button type="submit" size="lg" loading={busy} className="w-full">
        {label}
      </Button>
      <p className="text-center text-sm">
        <Link to="/login" className="font-medium text-navy-700 hover:text-navy-900">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}

// ----------------------------------------------------------- reset password

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(new ApiError(400, "password_mismatch", "The two passwords do not match."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password, confirm);
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <AuthLayout title="Password updated" subtitle="For your safety you were signed out on every device.">
        <ButtonLink to="/login" size="lg" className="w-full" iconRight="arrowRight">
          Sign in with your new password
        </ButtonLink>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password" subtitle="Use at least 8 characters. A short sentence works well.">
      {!token ? (
        <Alert>This link is missing its token. Request a new one from the sign in page.</Alert>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {error !== null && <Alert>{errorCode(error) === "invalid_token" ? "This link is invalid or has expired. Request a new one." : errorMessage(error)}</Alert>}
          <TextField label="New password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={password} onChange={(e) => setPassword(e.target.value)} />
          <TextField label="Confirm new password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <Button type="submit" size="lg" loading={busy} className="w-full">
            Update password
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}

// ------------------------------------------------------------- not found

export function NotFoundPage() {
  return (
    <div className="grid min-h-screen place-items-center bg-navy-50 px-6 text-center">
      <div>
        <p className="text-7xl font-bold text-navy-900">404</p>
        <p className="mt-3 text-lg font-medium text-navy-900">This page does not exist.</p>
        <p className="mt-1 text-sm text-slate-500">The link may be old, or the page has moved.</p>
        <div className="mt-8 flex justify-center gap-3">
          <ButtonLink to="/" variant="secondary">Home</ButtonLink>
          <ButtonLink to="/app">Dashboard</ButtonLink>
        </div>
      </div>
    </div>
  );
}
