import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "../api/tasks";
import { KanbanBoard } from "../components/KanbanBoard";
import type { TaskStatus } from "../api/types";

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const qc = useQueryClient();
  const [title, setTitle] = useState("");

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => tasksApi.list(projectId),
  });

  const createTask = useMutation({
    mutationFn: (t: string) => tasksApi.create(projectId, { title: t }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tasks", projectId] }); setTitle(""); },
  });

  const updateStatus = useMutation({
    mutationFn: ({ taskId, status }: { taskId: number; status: TaskStatus }) =>
      tasksApi.update(projectId, taskId, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", projectId] }),
  });

  if (isLoading) return <p>Loading tasks…</p>;

  return (
    <div style={{ maxWidth: 1200, margin: "40px auto", padding: 24 }}>
      <h1>Project #{projectId}</h1>
      <form
        onSubmit={(e) => { e.preventDefault(); if (title.trim()) createTask.mutate(title.trim()); }}
        style={{ display: "flex", gap: 8, marginBottom: 24 }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New task title" style={{ flex: 1 }} />
        <button type="submit">Add Task</button>
      </form>
      <KanbanBoard
        tasks={tasks ?? []}
        onStatusChange={(taskId, status) => updateStatus.mutate({ taskId, status })}
      />
    </div>
  );
}
