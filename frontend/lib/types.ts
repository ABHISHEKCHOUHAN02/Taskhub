export const taskStatuses = [
  "pending",
  "assigned",
  "in_progress",
  "submitted",
  "accepted",
  "revision_requested",
] as const;

export type TaskStatus = (typeof taskStatuses)[number];

export const generatedImageTypes = [
  "white_bg",
  "theme_marble",
  "theme_velvet",
  "creative_beach",
  "creative_studio",
  "model_front",
  "model_side",
  "model_closeup",
] as const;

export type GeneratedImageType = (typeof generatedImageTypes)[number];

export type Role = "admin" | "user";

export type UserSummary = {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: Role;
};

export type AdminUser = UserSummary & {
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type GeneratedImage = {
  id: string;
  task_id: string;
  image_type: GeneratedImageType;
  angle: string | null;
  image_bucket: string;
  image_url: string;
  prompt_used: string;
  metadata: Record<string, unknown>;
  is_final: boolean;
  created_by: string;
  created_at: string | null;
  updated_at: string | null;
};

export type Task = {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  created_by: string;
  assigned_to: string | null;
  creator: UserSummary | null;
  assignee: UserSummary | null;
  product_image_bucket: string;
  product_image_url: string;
  product_image_metadata: Record<string, unknown>;
  submission_notes: string | null;
  review_notes: string | null;
  due_at: string | null;
  assigned_at: string | null;
  started_at: string | null;
  submitted_at: string | null;
  accepted_at: string | null;
  revision_requested_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  generated_images?: GeneratedImage[];
};

export type AuditLog = {
  id: string;
  actor_user_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  before_data: Record<string, unknown>;
  after_data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string | null;
};

export type AuthMe = {
  authenticated: boolean;
  user: UserSummary & {
    is_active: boolean;
  };
};

export type TaskListResponse = {
  tasks: Task[];
};

export type TaskResponse = {
  task: Task;
};

export type GenerationsResponse = {
  generations: GeneratedImage[];
};

export type AuditLogsResponse = {
  audit_logs: AuditLog[];
};

export type AdminUsersResponse = {
  users: AdminUser[];
};

export type GenerationJobResponse = {
  job_id: string;
  state: string;
  ready: boolean;
  successful: boolean;
  result: unknown;
  error: string | null;
};
