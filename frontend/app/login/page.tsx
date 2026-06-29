import Link from "next/link";

type SearchParams = Promise<{
  oauth_error?: string;
  next?: string;
}>;

function errorLabel(code?: string) {
  switch (code) {
    case "provider_required":
      return "OAuth provider was not selected.";
    case "code_required":
      return "The OAuth callback did not include an authorization code.";
    case "invalid_state":
      return "OAuth state validation failed. Please sign in again.";
    case "token_exchange_failed":
      return "The OAuth provider did not return an access token.";
    case "oauth_profile_incomplete":
      return "The OAuth profile response was incomplete. Try signing in again.";
    default:
      return code ? `Login failed: ${code}` : null;
  }
}

export default async function LoginPage(props: { searchParams?: SearchParams }) {
  const searchParams = props.searchParams ? await props.searchParams : undefined;
  const error = errorLabel(searchParams?.oauth_error);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      <section className="mx-auto flex min-h-screen w-full max-w-4xl flex-col justify-center px-6 py-12 sm:px-10">
        <div className="grid gap-8 rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-black/30 backdrop-blur md:grid-cols-[1.1fr_0.9fr] md:p-10">
          <div className="space-y-5">
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-400">TaskHub</p>
            <h1 className="text-3xl font-semibold text-white">Sign in</h1>
            <p className="max-w-md text-sm leading-6 text-zinc-400">
              Use Google or GitHub to access your assigned tasks, admin tools, and AI studio. Email delivery is used for task notifications only.
            </p>
            {error ? (
              <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm leading-6 text-rose-100">
                {error}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-3 pt-2">
              <a
                className="rounded-full bg-white px-5 py-3 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
                href="/api/auth/oauth/google/start?next=/dashboard"
              >
                Continue with Google
              </a>
              <a
                className="rounded-full border border-zinc-700 px-5 py-3 text-sm font-medium text-white transition hover:border-zinc-500 hover:bg-zinc-900"
                href="/api/auth/oauth/github/start?next=/dashboard"
              >
                Continue with GitHub
              </a>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
            <p className="text-sm font-medium text-white">Need an account?</p>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              OAuth creates your user record the first time you sign in. Admin access is assigned by role after account creation.
            </p>
            <div className="mt-6 flex items-center gap-3">
              <Link
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                href="/register"
              >
                Go to Register
              </Link>
              <Link
                className="text-sm text-zinc-400 transition hover:text-white"
                href="/"
              >
                Back to home
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
