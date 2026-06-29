import { cookies } from "next/headers";
import Link from "next/link";

const workflowSteps = [
  {
    label: "Assign",
    text: "Admins create product photography tasks and assign them to users.",
  },
  {
    label: "Generate",
    text: "Users create the required 8 AI image variations for each product.",
  },
  {
    label: "Review",
    text: "Admins review submissions, accept work, or request revisions.",
  },
];

export default async function Home() {
  const cookieStore = await cookies();
  const role = cookieStore.get("taskhub_role")?.value;
  const userName = cookieStore.get("taskhub_user_name")?.value;
  const dashboardHref = role === "admin" ? "/admin" : "/dashboard";

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 py-6 sm:px-10 lg:px-12">
        <header className="flex flex-col gap-4 border-b border-white/10 py-4 sm:flex-row sm:items-center sm:justify-between">
          <Link className="text-lg font-semibold tracking-tight text-white" href="/">
            TaskHub
          </Link>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {role ? (
              <>
                <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1.5 font-medium text-emerald-200">
                  {userName ?? "Member"} - {role}
                </span>
                <Link
                  className="rounded-full bg-white px-4 py-2 font-medium text-zinc-950 transition hover:bg-zinc-200"
                  href={dashboardHref}
                >
                  Go to {role === "admin" ? "Admin" : "Dashboard"}
                </Link>
              </>
            ) : (
              <>
                <Link className="font-medium text-white/65 transition hover:text-white" href="/login">
                  Sign in
                </Link>
                <Link
                  className="rounded-full bg-white px-4 py-2 font-medium text-zinc-950 transition hover:bg-zinc-200"
                  href="/register"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </header>

        <div className="grid flex-1 gap-10 py-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-16">
          <section className="space-y-8">
            <div className="space-y-5">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-emerald-300">
                AI product photography workflow
              </p>
              <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl">
                Manage assignment tasks from brief to reviewed image set.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-white/65 sm:text-lg">
                TaskHub gives admins a clear task console and gives users a focused workspace for generating, selecting, and submitting product photography outputs.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-200"
                href={role ? dashboardHref : "/login"}
              >
                {role ? "Open workspace" : "Sign in to continue"}
              </Link>
              {!role ? (
                <Link
                  className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
                  href="/register"
                >
                  Create account
                </Link>
              ) : null}
            </div>

            <dl className="grid max-w-2xl grid-cols-3 gap-4 border-y border-white/10 py-5">
              <div>
                <dt className="text-2xl font-semibold text-white">8</dt>
                <dd className="mt-1 text-xs font-medium uppercase tracking-[0.16em] text-white/45">Required outputs</dd>
              </div>
              <div>
                <dt className="text-2xl font-semibold text-white">2</dt>
                <dd className="mt-1 text-xs font-medium uppercase tracking-[0.16em] text-white/45">User roles</dd>
              </div>
              <div>
                <dt className="text-2xl font-semibold text-white">SSR</dt>
                <dd className="mt-1 text-xs font-medium uppercase tracking-[0.16em] text-white/45">Protected pages</dd>
              </div>
            </dl>
          </section>

          <section className="grid gap-4">
            <div className="rounded-lg border border-white/10 bg-white/5 p-5 shadow-2xl shadow-black/30">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-white">Assignment workflow</p>
                  <p className="mt-1 text-sm leading-6 text-white/50">A compact path for reviewers to verify the core app behavior.</p>
                </div>
                <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200">
                  Live
                </span>
              </div>

              <div className="mt-6 grid gap-3">
                {workflowSteps.map((step, index) => (
                  <div className="flex gap-4 rounded-lg border border-white/10 bg-black/20 p-4" key={step.label}>
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-sm font-semibold text-zinc-950">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{step.label}</p>
                      <p className="mt-1 text-sm leading-6 text-white/60">{step.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-white/10 bg-white/5 p-5 shadow-2xl shadow-black/20">
                <p className="text-sm font-semibold text-white">Admin</p>
                <p className="mt-2 text-sm leading-6 text-white/60">
                  Create tasks, assign users, inspect submissions, and send review decisions.
                </p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-5 shadow-2xl shadow-black/20">
                <p className="text-sm font-semibold text-white">User</p>
                <p className="mt-2 text-sm leading-6 text-white/60">
                  Open assigned work, generate images, mark finals, and submit completed tasks.
                </p>
              </div>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
