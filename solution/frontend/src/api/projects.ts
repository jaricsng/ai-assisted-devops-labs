import apiClient from "./client";
import type { Project } from "./types";

export const projectsApi = {
  list: () => apiClient.get<Project[]>("/projects").then((r) => r.data),
  get: (id: number) => apiClient.get<Project>(`/projects/${id}`).then((r) => r.data),
  create: (payload: { name: string; description?: string }) =>
    apiClient.post<Project>("/projects", payload).then((r) => r.data),
  remove: (id: number) => apiClient.delete(`/projects/${id}`),
};
