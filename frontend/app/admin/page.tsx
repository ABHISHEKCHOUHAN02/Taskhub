import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AdminWorkspace } from "@/components/admin-workspace";
import { SignOutForm } from "@/components/sign-out-form";
import { getAdminTasks, getAdminUsers, getAuthMe } from "@/lib/api";
import type { AdminUsersResponse, TaskListResponse } from "@/lib/types";

export default async function AdminPage() {
  const cookieStore = await cookies();
  const role = cookieStore.get("taskhub_role")?.value;

  if (!role) {
    redirect("/");
  }

  if (role !== "admin") {
    redirect("/dashboard");
  }

  const auth = await getAuthMe().catch(() => null);
  if (!auth?.authenticated) {
    redirect("/login");
  }

  let taskResponse: TaskListResponse = { tasks: [] };
  let userResponse: AdminUsersResponse = { users: [] };
  let loadError: string | null = null;

  try {
    [taskResponse, userResponse] = await Promise.all([getAdminTasks(), getAdminUsers()]);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load admin data";
    loadError = message;
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-4 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.24em] text-white/45">TaskHub</p>
            <h1 className="text-xl font-semibold text-white">Admin dashboard</h1>
            <p className="text-sm text-white/50">Live task operations and user management.</p>
          </div>
          <div className="flex items-center gap-3">
            <SignOutForm />
          </div>
        </header>

        {loadError ? (
          <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-5 text-sm text-rose-200">
            {loadError}
          </div>
        ) : (
          <AdminWorkspace tasks={taskResponse.tasks} users={userResponse.users} />
        )}
      </section>
    </main>
  );
}
