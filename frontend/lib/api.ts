import { cookies, headers } from "next/headers";

import type {
  AdminUsersResponse,
  AuditLogsResponse,
  AuthMe,
  GenerationJobResponse,
  GenerationsResponse,
  TaskListResponse,
  TaskResponse,
} from "./types";

function resolveApiBaseUrl() {
  const configured =
    process.env.INTERNAL_API_BASE_URL ||
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:5000";

  try {
    const parsed = new URL(configured);
    if ((parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") && parsed.port === "3000") {
      return "http://127.0.0.1:5000";
    }
  } catch {
    // Fall through to the configured value when it is not a full URL.
  }

  return configured;
}

export const API_BASE_URL = resolveApiBaseUrl();

async function cookieHeader(): Promise<string> {
  const cookieStore = await cookies();
  return cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

async function defaultHeaders() {
  const headerStore = await headers();
  const forwardedHost = headerStore.get("x-forwarded-host");
  const origin = forwardedHost ? `http://${forwardedHost}` : undefined;
  return {
    Cookie: await cookieHeader(),
    ...(origin ? { Origin: origin } : {}),
  };
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    const message =
      body.includes("<html") || body.includes("<!doctype html")
        ? `Backend request failed with ${response.status} ${response.statusText}`
        : body || response.statusText || "Request failed";
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function fetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headersValue = await defaultHeaders();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      ...headersValue,
      ...(init.headers || {}),
    },
  });
  return parseResponse<T>(response);
}

export async function getAuthMe(): Promise<AuthMe> {
  return fetchJson<AuthMe>("/api/auth/me");
}

export async function getTasks(): Promise<TaskListResponse> {
  return fetchJson<TaskListResponse>("/api/my-tasks");
}

export async function getAdminTasks(): Promise<TaskListResponse> {
  return fetchJson<TaskListResponse>("/api/admin/tasks");
}

export async function getAdminUsers(): Promise<AdminUsersResponse> {
  return fetchJson<AdminUsersResponse>("/api/auth/admin/users");
}

export async function getTask(taskId: string): Promise<TaskResponse> {
  return fetchJson<TaskResponse>(`/api/tasks/${taskId}`);
}

export async function getTaskGenerations(taskId: string): Promise<GenerationsResponse> {
  return fetchJson<GenerationsResponse>(`/api/tasks/${taskId}/generations`);
}

export async function getTaskAuditLogs(taskId: string): Promise<AuditLogsResponse> {
  return fetchJson<AuditLogsResponse>(`/api/tasks/${taskId}/audit-logs`);
}

export async function getJobStatus(jobId: string): Promise<GenerationJobResponse> {
  return fetchJson<GenerationJobResponse>(`/api/jobs/${jobId}/status`);
}
