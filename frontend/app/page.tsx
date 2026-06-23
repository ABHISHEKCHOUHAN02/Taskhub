import { cookies } from "next/headers";
import Link from "next/link";

export default async function Home() {
  const cookieStore = await cookies();
  const role = cookieStore.get("taskhub_role")?.value;
  const userName = cookieStore.get("taskhub_user_name")?.value;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      <section className="mx-auto flex min-h-screen w-full max-w-6xl flex-col justify-between px-6 py-8 sm:px-10 lg:px-12">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-400">TaskHub</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">AI product photography workflow</h1>
          </div>
          <div className="text-right text-sm text-zinc-300">
            {role ? (
              <>
                <p>Signed in as {userName ?? "member"}</p>
                <p className="text-zinc-500">Role: {role}</p>
              </>
            ) : (
              <p>Public access</p>
            )}
          </div>
        </header>

        <div className="grid gap-10 py-16 lg:grid-cols-[1.3fr_0.9fr] lg:items-center">
          <div className="space-y-6">
            <p className="max-w-xl text-sm leading-6 text-zinc-400">
              Assign product photography tasks, generate 8 AI variations, review submissions, and keep the product identical across every output.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-full bg-white px-5 py-3 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
                href="/login"
              >
                Sign in
              </Link>
              <Link
                className="rounded-full border border-zinc-700 px-5 py-3 text-sm font-medium text-white transition hover:border-zinc-500 hover:bg-zinc-900"
                href="/register"
              >
                Register
              </Link>
              <a
                className="rounded-full border border-white/10 px-5 py-3 text-sm font-medium text-white transition hover:bg-white/10"
                href="/api/auth/oauth/google/start"
              >
                Google OAuth
              </a>
              <a
                className="rounded-full border border-white/10 px-5 py-3 text-sm font-medium text-white transition hover:bg-white/10"
                href="/api/auth/oauth/github/start"
              >
                GitHub OAuth
              </a>
              {role ? (
                <Link
                  className="rounded-full border border-emerald-500/40 px-5 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/10"
                  href={role === "admin" ? "/admin" : "/dashboard"}
                >
                  Go to {role === "admin" ? "Admin" : "Dashboard"}
                </Link>
              ) : null}
            </div>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/30 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Access rules</p>
            <div className="mt-6 space-y-4 text-sm text-zinc-300">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="font-medium text-white">Admin</p>
                <p className="mt-1">Create and assign tasks, review submissions, and see platform data.</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="font-medium text-white">User</p>
                <p className="mt-1">See assigned tasks, generate images, and submit completed work.</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
