import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { SignOutForm } from "../../components/sign-out-form";

export default async function AdminPage() {
  const cookieStore = await cookies();
  const role = cookieStore.get("taskhub_role")?.value;

  if (!role) {
    redirect("/");
  }

  if (role !== "admin") {
    redirect("/dashboard");
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-50">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-zinc-400">TaskHub</p>
            <h1 className="text-xl font-semibold">Admin Dashboard</h1>
          </div>
          <SignOutForm />
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-sm text-zinc-400">All tasks</p>
            <p className="mt-3 text-3xl font-semibold">0</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-sm text-zinc-400">Pending review</p>
            <p className="mt-3 text-3xl font-semibold">0</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-sm text-zinc-400">Analytics</p>
            <p className="mt-3 text-3xl font-semibold">0</p>
          </div>
        </section>
      </section>
    </main>
  );
}
