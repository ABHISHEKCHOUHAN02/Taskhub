import Link from "next/link";

export default function RegisterPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      <section className="mx-auto flex min-h-screen w-full max-w-4xl flex-col justify-center px-6 py-12 sm:px-10">
        <div className="grid gap-8 rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-black/30 backdrop-blur md:grid-cols-[1.1fr_0.9fr] md:p-10">
          <div className="space-y-5">
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-400">TaskHub</p>
            <h1 className="text-3xl font-semibold text-white">Create your account</h1>
            <p className="max-w-md text-sm leading-6 text-zinc-400">
              New users join with Google or GitHub. The first OAuth sign-in creates the account automatically.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <a
                className="rounded-full bg-white px-5 py-3 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
                href="/api/auth/oauth/google/start?next=/dashboard"
              >
                Register with Google
              </a>
              <a
                className="rounded-full border border-zinc-700 px-5 py-3 text-sm font-medium text-white transition hover:border-zinc-500 hover:bg-zinc-900"
                href="/api/auth/oauth/github/start?next=/dashboard"
              >
                Register with GitHub
              </a>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
            <p className="text-sm font-medium text-white">Already have access?</p>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              Use the same OAuth provider to sign in. Admin access is role-based and assigned on the backend.
            </p>
            <div className="mt-6 flex items-center gap-3">
              <Link
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                href="/login"
              >
                Go to Login
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
