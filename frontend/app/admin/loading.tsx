export default function Loading() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-4 sm:px-6 lg:px-8">
        <div className="h-24 animate-pulse rounded-2xl border border-white/10 bg-white/5" />
        <div className="grid gap-4 md:grid-cols-3">
          <div className="h-28 animate-pulse rounded-2xl border border-white/10 bg-white/5" />
          <div className="h-28 animate-pulse rounded-2xl border border-white/10 bg-white/5" />
          <div className="h-28 animate-pulse rounded-2xl border border-white/10 bg-white/5" />
        </div>
        <div className="h-[36rem] animate-pulse rounded-2xl border border-white/10 bg-white/5" />
      </section>
    </main>
  );
}
