import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

import { SignOutForm } from "@/components/sign-out-form";
import { TaskStudio } from "@/components/task-studio";
import { getAuthMe, getTask, getTaskAuditLogs, getTaskGenerations } from "@/lib/api";
import type { AuditLogsResponse, GenerationsResponse, TaskResponse } from "@/lib/types";

type Params = Promise<{ task_id: string }>;

export default async function TaskDetailPage(props: { params: Params }) {
  const { task_id } = await props.params;
  const cookieStore = await cookies();
  const role = cookieStore.get("taskhub_role")?.value;

  if (!role) {
    redirect("/");
  }

  const auth = await getAuthMe().catch(() => null);
  if (!auth?.authenticated) {
    redirect("/login");
  }

  let taskResponse: TaskResponse | null = null;
  let generationsResponse: GenerationsResponse = { generations: [] };
  let auditResponse: AuditLogsResponse = { audit_logs: [] };
  let loadError: string | null = null;

  try {
    [taskResponse, generationsResponse, auditResponse] = await Promise.all([
      getTask(task_id),
      getTaskGenerations(task_id),
      getTaskAuditLogs(task_id),
    ]);
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Unable to load task";
  }

  const task = taskResponse?.task;

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-4 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.24em] text-white/45">TaskHub</p>
            <h1 className="text-xl font-semibold text-white">Task detail</h1>
            <p className="text-sm text-white/50">
              <Link href={role === "admin" ? "/admin" : "/dashboard"} className="underline underline-offset-4">
                Back to {role === "admin" ? "admin" : "dashboard"}
              </Link>
            </p>
          </div>
          <div className="flex items-center gap-3">
            <SignOutForm />
          </div>
        </header>

        {loadError || !task ? (
          <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-200">
            {loadError || "Task data could not be loaded."}
          </div>
        ) : (
          <TaskStudio task={task} generations={generationsResponse.generations} auditLogs={auditResponse.audit_logs} />
        )}
      </section>
    </main>
  );
}
