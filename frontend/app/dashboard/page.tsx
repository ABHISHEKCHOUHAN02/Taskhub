import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

import { SignOutForm } from "@/components/sign-out-form";
import { getAuthMe, getTasks } from "@/lib/api";
import type { Task, TaskListResponse } from "@/lib/types";

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const role = cookieStore.get("taskhub_role")?.value;

  if (!role) {
    redirect("/");
  }

  if (role === "admin") {
    redirect("/admin");
  }

  const auth = await getAuthMe().catch(() => null);
  if (!auth?.authenticated) {
    redirect("/login");
  }

  let taskResponse: TaskListResponse = { tasks: [] };
  let loadError: string | null = null;

  try {
    taskResponse = await getTasks();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load tasks";
    loadError = message;
  }

  const tasks = taskResponse.tasks;
  const assigned = tasks.filter((task) => task.status === "assigned" || task.status === "in_progress" || task.status === "revision_requested");
  const submitted = tasks.filter((task) => task.status === "submitted");
  const completed = tasks.filter((task) => task.status === "accepted");

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-4 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.24em] text-white/45">TaskHub</p>
            <h1 className="text-xl font-semibold text-white">User dashboard</h1>
            <p className="text-sm text-white/50">Assigned work and live generation status.</p>
          </div>
          <div className="flex items-center gap-3">
            <SignOutForm />
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <StatCard label="Assigned tasks" value={assigned.length} />
          <StatCard label="Submitted" value={submitted.length} />
          <StatCard label="Accepted" value={completed.length} />
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-sm">
          {loadError ? (
            <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-200">
              {loadError}
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-white/45">Tasks</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Your queue</h2>
                </div>
                <p className="text-sm text-white/50">{tasks.length} total</p>
              </div>

              <div className="mt-4 grid gap-4">
                {tasks.length ? (
                  tasks.map((task) => <TaskRow key={task.id} task={task} />)
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 p-6 text-sm text-white/50">
                    No assigned tasks yet.
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-sm">
      <p className="text-sm text-white/50">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
    </div>
  );
}

function TaskRow({ task }: { task: Task }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-white">{task.title}</h3>
            <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-white/60">
              {task.status.replaceAll("_", " ")}
            </span>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-white/60">{task.description || "No description provided."}</p>
          <p className="text-xs text-white/45">
            {task.generated_images?.length ?? 0}/8 generated
          </p>
        </div>
        <Link
          href={`/tasks/${task.id}`}
          className="inline-flex items-center justify-center rounded-full bg-white px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
        >
          Open task
        </Link>
      </div>
    </article>
  );
}
