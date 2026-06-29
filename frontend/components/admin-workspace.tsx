"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { AdminUser, Task } from "@/lib/types";

type Props = {
  tasks: Task[];
  users: AdminUser[];
};

const MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024;

function formatCreateTaskError(code?: string, message?: string) {
  switch (code) {
    case "storage_not_configured":
      return message || "Storage is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env.";
    case "storage_bucket_setup_failed":
      return message || "Could not prepare the Supabase storage bucket. Create a public bucket named taskhub-assets in Supabase.";
    case "storage_upload_failed":
      return message || "Image upload failed. Verify your Supabase service role key and storage bucket settings.";
    case "product_image_required":
      return "Upload a product image before creating the task.";
    case "product_image_type_invalid":
      return "Please upload a supported image type (JPG, PNG, WEBP, or GIF).";
    case "product_image_too_large":
      return "Image must be 10 MB or smaller.";
    case "title_required":
      return "Task title is required.";
    case "assigned_to_invalid":
      return "Selected assignee is invalid.";
    case "due_at_invalid":
      return message || "Due date must be a valid date and time, or leave the field empty.";
    case "task_create_failed":
      return message || "Task could not be created. Check the backend logs for details.";
    default:
      return message || code || "Create failed";
  }
}

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AdminWorkspace({ tasks, users }: Props) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "",
    description: "",
    assigned_to: "",
    due_at: "",
  });
  const [productImageFile, setProductImageFile] = useState<File | null>(null);

  const taskCounts = useMemo(
    () => ({
      total: tasks.length,
      pending: tasks.filter((task) => task.status === "pending").length,
      submitted: tasks.filter((task) => task.status === "submitted").length,
    }),
    [tasks],
  );

  const productImagePreview = useMemo(() => (productImageFile ? URL.createObjectURL(productImageFile) : null), [productImageFile]);

  useEffect(() => {
    return () => {
      if (productImagePreview) {
        URL.revokeObjectURL(productImagePreview);
      }
    };
  }, [productImagePreview]);

  async function api(path: string, init: RequestInit = {}) {
    setError(null);
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers || {}),
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error || response.statusText || "Request failed");
    }
    return response.json();
  }

  function resetCreateForm() {
    setCreateForm({ title: "", description: "", assigned_to: "", due_at: "" });
    setProductImageFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleProductImageChange(file: File | null) {
    if (!file) {
      setProductImageFile(null);
      return;
    }

    if (!file.type.startsWith("image/")) {
      throw new Error("Please choose an image file (JPG, PNG, WEBP, or GIF).");
    }
    if (file.size > MAX_PRODUCT_IMAGE_BYTES) {
      throw new Error("Image must be 10 MB or smaller.");
    }

    setProductImageFile(file);
  }

  async function createTask() {
    if (isCreatingTask) {
      return;
    }

    const title = createForm.title.trim();
    if (!title) {
      throw new Error("Task title is required.");
    }
    if (!productImageFile) {
      throw new Error("Upload a product image before creating the task.");
    }

    const formData = new FormData();
    formData.append("title", title);
    formData.append("description", createForm.description);
    formData.append("product_image_file", productImageFile);
    if (createForm.assigned_to) {
      formData.append("assigned_to", createForm.assigned_to);
    }
    if (createForm.due_at) {
      const dueAt = new Date(createForm.due_at);
      if (Number.isNaN(dueAt.getTime())) {
        throw new Error("Due date must be a valid date and time, or leave the field empty.");
      }
      formData.append("due_at", dueAt.toISOString());
    }

    setError(null);
    setIsCreatingTask(true);
    try {
      const response = await fetch("/api/admin/tasks", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(formatCreateTaskError(payload?.error, payload?.message));
      }

      resetCreateForm();
      router.refresh();
    } finally {
      setIsCreatingTask(false);
    }
  }

  async function assignTask(taskId: string, assignedTo: string) {
    await api(`/api/admin/tasks/${taskId}/assign`, {
      method: "POST",
      body: JSON.stringify({ assigned_to: assignedTo }),
    });
    router.refresh();
  }

  async function acceptTask(taskId: string) {
    await api(`/api/admin/tasks/${taskId}/accept`, {
      method: "POST",
      body: JSON.stringify({ review_notes: "Accepted from admin dashboard." }),
    });
    router.refresh();
  }

  async function requestRevision(taskId: string) {
    await api(`/api/admin/tasks/${taskId}/request-revision`, {
      method: "POST",
      body: JSON.stringify({ review_notes: "Please revise the output." }),
    });
    router.refresh();
  }

  async function deleteTask(taskId: string) {
    await api(`/api/admin/tasks/${taskId}`, { method: "DELETE" });
    router.refresh();
  }

  async function updateUser(userId: string, nextRole: string, isActive: boolean) {
    await api(`/api/auth/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role: nextRole, is_active: isActive }),
    });
    router.refresh();
  }

  function runAction(action: () => Promise<void>) {
    void action().catch((err) => setError(err instanceof Error ? err.message : "Request failed"));
  }

  const canCreateTask = Boolean(createForm.title.trim() && productImageFile && !isCreatingTask);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm text-white/45">All tasks</p>
          <p className="mt-2 text-3xl font-semibold text-white">{taskCounts.total}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm text-white/45">Pending review</p>
          <p className="mt-2 text-3xl font-semibold text-white">{taskCounts.submitted}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-sm text-white/45">Pending</p>
          <p className="mt-2 text-3xl font-semibold text-white">{taskCounts.pending}</p>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-white/45">Create task</p>
              <h2 className="mt-1 text-lg font-semibold text-white">New assignment</h2>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <input
              value={createForm.title}
              onChange={(event) => setCreateForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="Title"
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none"
            />
            <select
              value={createForm.assigned_to}
              onChange={(event) => setCreateForm((current) => ({ ...current, assigned_to: event.target.value }))}
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none"
            >
              <option value="">Unassigned</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name || user.email}
                </option>
              ))}
            </select>
            <textarea
              value={createForm.description}
              onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="Description"
              className="min-h-28 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none md:col-span-2"
            />
            <input
              type="datetime-local"
              value={createForm.due_at}
              onChange={(event) => setCreateForm((current) => ({ ...current, due_at: event.target.value }))}
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none md:col-span-2 [color-scheme:dark]"
            />
            <div className="rounded-xl border border-dashed border-white/15 bg-black/20 p-4 md:col-span-2">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-white">Product image</p>
                  <p className="text-xs leading-5 text-white/45">
                    Upload the source product photo from your computer. JPG, PNG, WEBP, or GIF up to 10 MB.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <label className="inline-flex cursor-pointer items-center rounded-full bg-white px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200">
                      {productImageFile ? "Change image" : "Choose image"}
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/gif,image/bmp,image/tiff"
                        onChange={(event) => {
                          try {
                            handleProductImageChange(event.target.files?.[0] ?? null);
                            setError(null);
                          } catch (err) {
                            setError(err instanceof Error ? err.message : "Invalid image file");
                            setProductImageFile(null);
                            if (fileInputRef.current) {
                              fileInputRef.current.value = "";
                            }
                          }
                        }}
                        className="hidden"
                      />
                    </label>
                    {productImageFile ? (
                      <button
                        type="button"
                        onClick={() => {
                          setProductImageFile(null);
                          if (fileInputRef.current) {
                            fileInputRef.current.value = "";
                          }
                        }}
                        className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                  {productImageFile ? (
                    <p className="text-xs text-white/55">
                      {productImageFile.name} ({formatFileSize(productImageFile.size)})
                    </p>
                  ) : null}
                </div>
                {productImagePreview ? (
                  <div className="overflow-hidden rounded-xl border border-white/10 bg-black/30">
                    <img src={productImagePreview} alt="Product preview" className="h-32 w-32 object-cover sm:h-36 sm:w-36" />
                  </div>
                ) : (
                  <div className="flex h-32 w-32 items-center justify-center rounded-xl border border-white/10 bg-black/30 text-xs text-white/35 sm:h-36 sm:w-36">
                    No preview
                  </div>
                )}
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled={!canCreateTask}
            onClick={() => void createTask().catch((err) => setError(err instanceof Error ? err.message : "Create failed"))}
            className="mt-4 rounded-full bg-white px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-white/20 disabled:text-white/50"
          >
            {isCreatingTask ? "Creating..." : "Create task"}
          </button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-white/45">Users</p>
          <div className="mt-4 space-y-3">
            {users.map((user) => (
              <div key={user.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-white">{user.full_name || user.email}</p>
                    <p className="text-xs text-white/45">{user.email}</p>
                  </div>
                  <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/70">{user.role}</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => updateUser(user.id, user.role === "admin" ? "user" : "admin", user.is_active)}
                    className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/10"
                  >
                    Toggle role
                  </button>
                  <button
                    type="button"
                    onClick={() => updateUser(user.id, user.role, !user.is_active)}
                    className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/10"
                  >
                    {user.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
        <p className="text-xs uppercase tracking-[0.24em] text-white/45">Tasks</p>
        <div className="mt-4 grid gap-4">
          {tasks.map((task) => {
            const assignee = task.assignee?.full_name || task.assignee?.email || "Unassigned";
            return (
              <article key={task.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-lg font-semibold text-white">{task.title}</p>
                    <p className="mt-1 text-sm text-white/60">{task.description || "No description"}</p>
                  </div>
                  <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/70">{statusLabel(task.status)}</span>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/70">
                    <p className="text-white/45">Assignee</p>
                    <p className="mt-1">{assignee}</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/70">
                    <p className="text-white/45">Images</p>
                    <p className="mt-1">{task.generated_images?.length ?? 0}/8</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/70">
                    <p className="text-white/45">Open</p>
                    <a className="mt-1 inline-block text-white underline" href={`/tasks/${task.id}`}>
                      Task detail
                    </a>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <select
                    defaultValue={task.assigned_to ?? ""}
                    onChange={(event) => {
                      if (event.target.value) {
                        runAction(() => assignTask(task.id, event.target.value));
                      }
                    }}
                    className="rounded-full border border-white/10 bg-black/20 px-3 py-2 text-xs text-white outline-none"
                  >
                    <option value="">Assign to...</option>
                    {users.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.full_name || user.email}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => runAction(() => acceptTask(task.id))}
                    className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    onClick={() => runAction(() => requestRevision(task.id))}
                    className="rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
                  >
                    Request revision
                  </button>
                  <button
                    type="button"
                    onClick={() => runAction(() => deleteTask(task.id))}
                    className="rounded-full border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100"
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">{error}</div> : null}
      {isCreatingTask ? <p className="text-sm text-white/45">Saving changes...</p> : null}
    </div>
  );
}
