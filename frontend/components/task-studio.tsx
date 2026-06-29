"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type { AuditLog, GeneratedImage, GeneratedImageType, Task } from "@/lib/types";
import { generatedImageTypes } from "@/lib/types";

type Props = {
  task: Task;
  generations: GeneratedImage[];
  auditLogs: AuditLog[];
};

type JobState = {
  jobId: string;
  imageType: GeneratedImageType;
  state: string;
  step?: string | null;
  error?: string | null;
};

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

function finalCount(generations: GeneratedImage[]) {
  return generations.filter((generation) => generation.is_final).length;
}

function formatTaskStudioError(code?: string, message?: string) {
  switch (code) {
    case "generation_queue_unavailable":
      return message || "Image generation queue is unavailable. Start Redis and the Celery worker, then try again.";
    case "generation_status_unavailable":
      return message || "Image generation status is unavailable. Check Redis and the Celery worker.";
    case "accepted_task_cannot_generate":
      return "Accepted tasks cannot generate new images.";
    case "task_not_found":
      return "This task is not available for your account.";
    case "task_generation_incomplete":
      return "Generate all 8 required images before submitting.";
    case "task_generation_not_finalized":
      return "Mark all 8 generated images as final before submitting.";
    default:
      return message || code || "Request failed";
  }
}

export function TaskStudio({ task, generations, auditLogs }: Props) {
  const router = useRouter();
  const [notes, setNotes] = useState(task.submission_notes ?? "");
  const [reviewNotes, setReviewNotes] = useState(task.review_notes ?? "");
  const [jobs, setJobs] = useState<JobState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [generatingTypes, setGeneratingTypes] = useState<Set<GeneratedImageType>>(new Set());
  const [isPending, startTransition] = useTransition();

  const generationMap = useMemo(() => {
    const map = new Map<GeneratedImageType, GeneratedImage>();
    for (const generation of generations) {
      map.set(generation.image_type, generation);
    }
    return map;
  }, [generations]);

  const progress = `${finalCount(generations)}/8`;
  const canSubmit = finalCount(generations) === 8 && generations.every((generation) => generation.is_final);

  async function mutate(path: string, body?: Record<string, unknown>) {
    setError(null);
    const response = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(formatTaskStudioError(payload?.error, payload?.message || response.statusText));
    }
    return response.json();
  }

  async function deleteGeneration(path: string) {
    setError(null);
    const response = await fetch(path, { method: "DELETE" });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error || response.statusText || "Delete failed");
    }
    return response.json();
  }

  async function generateVariant(imageType: GeneratedImageType) {
    if (generatingTypes.has(imageType)) {
      return;
    }

    setGeneratingTypes((current) => new Set(current).add(imageType));
    try {
      const payload = await mutate(`/api/tasks/${task.id}/generations`, { image_type: imageType });
      const firstJob = payload?.jobs?.[0];
      if (firstJob?.job_id) {
        setJobs((current) => [...current, { jobId: firstJob.job_id, imageType, state: firstJob.state ?? "PENDING" }]);
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGeneratingTypes((current) => {
        const next = new Set(current);
        next.delete(imageType);
        return next;
      });
    }
  }

  async function startTask() {
    try {
      await mutate(`/api/tasks/${task.id}/start`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start task");
    }
  }

  async function submitTask() {
    try {
      await mutate(`/api/tasks/${task.id}/submit`, { submission_notes: notes });
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit task");
    }
  }

  async function markFinal(generationId: string) {
    try {
      await mutate(`/api/tasks/${task.id}/generations/${generationId}/mark-final`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not mark final");
    }
  }

  async function deleteImage(generationId: string) {
    try {
      await deleteGeneration(`/api/tasks/${task.id}/generations/${generationId}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete image");
    }
  }

  useEffect(() => {
    if (!jobs.length) {
      return;
    }

    const timer = window.setInterval(async () => {
      const nextJobs: JobState[] = [];
      let refresh = false;

      for (const job of jobs) {
        try {
          const response = await fetch(`/api/jobs/${job.jobId}/status`);
          if (!response.ok) {
            const payload = await response.json().catch(() => null);
            nextJobs.push({
              ...job,
              error: formatTaskStudioError(payload?.error, payload?.message || response.statusText),
            });
            continue;
          }
          const status = (await response.json()) as {
            state: string;
            successful: boolean;
            meta?: { step?: string | null } | null;
            error: string | null;
          };
          if (status.successful) {
            refresh = true;
            continue;
          }
          if (status.state === "FAILURE") {
            nextJobs.push({ ...job, state: status.state, step: status.meta?.step ?? job.step, error: status.error });
          } else {
            nextJobs.push({ ...job, state: status.state, step: status.meta?.step ?? job.step, error: null });
          }
        } catch {
          nextJobs.push({
            ...job,
            error: "Status check unavailable. Retrying...",
          });
          continue;
        }
      }

      setJobs(nextJobs);
      if (refresh) {
        router.refresh();
      }
    }, 3000);

    return () => window.clearInterval(timer);
  }, [jobs, router]);

  return (
    <div className="grid gap-6 xl:grid-cols-[1.4fr_0.8fr]">
      <section className="space-y-6">
        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5">
            <img src={task.product_image_url} alt={task.title} className="h-full w-full object-cover" />
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-white/45">Task</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">{task.title}</h1>
            <p className="mt-3 text-sm leading-6 text-white/70">{task.description || "No description provided."}</p>
            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                <p className="text-white/45">Status</p>
                <p className="mt-1 font-medium text-white">{statusLabel(task.status)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                <p className="text-white/45">Progress</p>
                <p className="mt-1 font-medium text-white">{progress}</p>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              {(task.status === "assigned" || task.status === "revision_requested") && (
                <button
                  type="button"
                  onClick={() => startTransition(() => void startTask())}
                  className="rounded-full bg-white px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200"
                >
                  {isPending ? "Starting..." : "Start task"}
                </button>
              )}
              <button
                type="button"
                onClick={() => generateVariant(generatedImageTypes[0])}
                disabled={generatingTypes.has(generatedImageTypes[0])}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/45"
              >
                {generatingTypes.has(generatedImageTypes[0]) ? "Queueing..." : "Generate white bg"}
              </button>
              <button
                type="button"
                onClick={() => generateVariant(generatedImageTypes[5])}
                disabled={generatingTypes.has(generatedImageTypes[5])}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/45"
              >
                {generatingTypes.has(generatedImageTypes[5]) ? "Queueing..." : "Generate model"}
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-white/45">AI Studio</p>
              <h2 className="mt-1 text-lg font-semibold text-white">Required variants</h2>
            </div>
            <p className="text-sm text-white/60">{progress} finalized</p>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {generatedImageTypes.map((imageType) => {
              const generation = generationMap.get(imageType);
              return (
                <article key={imageType} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">{imageType.replaceAll("_", " ")}</p>
                      <p className="mt-1 text-xs text-white/45">{generation?.angle ?? "Not generated yet"}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => generateVariant(imageType)}
                      disabled={generatingTypes.has(imageType)}
                      className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/45"
                    >
                      {generatingTypes.has(imageType) ? "Queueing..." : generation ? "Regenerate" : "Generate"}
                    </button>
                  </div>

                  {generation ? (
                    <div className="mt-4 space-y-3">
                      <img src={generation.image_url} alt={imageType} className="h-44 w-full rounded-xl object-cover" />
                      <p className="text-xs leading-5 text-white/60">{generation.prompt_used}</p>
                      <div className="flex flex-wrap gap-2">
                        <a className="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-zinc-950" href={generation.image_url} target="_blank" rel="noreferrer">
                          View
                        </a>
                        <a className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white" href={generation.image_url} download>
                          Download
                        </a>
                        <button
                          type="button"
                          onClick={() => markFinal(generation.id)}
                          className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                            generation.is_final ? "bg-emerald-500 text-white" : "border border-emerald-400/40 bg-emerald-500/10 text-emerald-200"
                          }`}
                        >
                          {generation.is_final ? "Final" : "Mark final"}
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteImage(generation.id)}
                          className="rounded-full border border-rose-400/40 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-200"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 rounded-xl border border-dashed border-white/10 bg-white/5 p-4 text-sm text-white/55">
                      No image yet. Generate this variant to continue.
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-white/45">Submission</p>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Submission notes"
            className="mt-3 min-h-32 w-full rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white outline-none placeholder:text-white/30"
          />
          <button
            type="button"
            onClick={submitTask}
            disabled={!canSubmit}
            className="mt-3 w-full rounded-full bg-white px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-white/20"
          >
            {canSubmit ? "Submit completed task" : "Generate and finalize all 8 images"}
          </button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-white/45">Review notes</p>
          <textarea
            value={reviewNotes}
            onChange={(event) => setReviewNotes(event.target.value)}
            placeholder="Review notes"
            className="mt-3 min-h-28 w-full rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white outline-none placeholder:text-white/30"
          />
          <p className="mt-3 text-xs text-white/45">Admin review flow is handled on the backend. This panel surfaces the current note field only.</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-white/45">Generation Jobs</p>
          <div className="mt-4 space-y-3">
            {jobs.length ? (
              jobs.map((job) => (
                <div key={job.jobId} className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm">
                  <p className="font-medium text-white">{job.imageType.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-white/55">Job {job.jobId}</p>
                  <p className="mt-1 text-white/55">
                    {job.state}
                    {job.step ? ` - ${job.step}` : ""}
                    {job.error ? ` - ${job.error}` : ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-white/45">No active jobs.</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-white/45">Audit trail</p>
          <div className="mt-4 space-y-3">
            {auditLogs.slice(0, 6).map((log) => (
              <div key={log.id} className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm">
                <p className="font-medium text-white">{log.action}</p>
                <p className="mt-1 text-white/55">{log.created_at ?? ""}</p>
              </div>
            ))}
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </div>
        ) : null}
      </aside>
    </div>
  );
}
