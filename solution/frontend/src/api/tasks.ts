import apiClient from "./client";
import type { Task, TaskStatus, TaskPriority, Comment } from "./types";

export const tasksApi = {
  list: (projectId: number) =>
    apiClient.get<Task[]>(`/projects/${projectId}/tasks`).then((r) => r.data),
  create: (
    projectId: number,
    payload: { title: string; description?: string; priority?: TaskPriority }
  ) => apiClient.post<Task>(`/projects/${projectId}/tasks`, payload).then((r) => r.data),
  update: (
    projectId: number,
    taskId: number,
    payload: { status?: TaskStatus; title?: string; priority?: TaskPriority }
  ) => apiClient.patch<Task>(`/projects/${projectId}/tasks/${taskId}`, payload).then((r) => r.data),
  remove: (projectId: number, taskId: number) =>
    apiClient.delete(`/projects/${projectId}/tasks/${taskId}`),
  listComments: (projectId: number, taskId: number) =>
    apiClient.get<Comment[]>(`/projects/${projectId}/tasks/${taskId}/comments`).then((r) => r.data),
  addComment: (projectId: number, taskId: number, body: string) =>
    apiClient.post<Comment>(`/projects/${projectId}/tasks/${taskId}/comments`, { body }).then((r) => r.data),
};
