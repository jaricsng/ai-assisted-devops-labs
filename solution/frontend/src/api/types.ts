// Generated from docs/api/openapi.yaml — run: npx openapi-typescript docs/api/openapi.yaml -o frontend/src/api/types.ts

export type TaskStatus = "TODO" | "IN_PROGRESS" | "IN_REVIEW" | "DONE" | "CANCELLED";
export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface User {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  owner_id: number;
  created_at: string;
}

export interface Task {
  id: number;
  project_id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id: number | null;
  due_date: string | null;
  created_at: string;
}

export interface Comment {
  id: number;
  task_id: number;
  author_id: number;
  body: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}
