import type { Task, TaskStatus } from "../api/types";

interface Props {
  task: Task;
  onStatusChange: (taskId: number, status: TaskStatus) => void;
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  TODO: "To Do",
  IN_PROGRESS: "In Progress",
  IN_REVIEW: "In Review",
  DONE: "Done",
  CANCELLED: "Cancelled",
};

const PRIORITY_COLORS: Record<Task["priority"], string> = {
  LOW: "#6b7280",
  MEDIUM: "#2563eb",
  HIGH: "#d97706",
  URGENT: "#dc2626",
};

export function TaskCard({ task, onStatusChange }: Props) {
  const nextStatuses: TaskStatus[] = getNextStatuses(task.status);

  return (
    <div data-testid={`task-card-${task.id}`} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <strong>{task.title}</strong>
        <span style={{ color: PRIORITY_COLORS[task.priority], fontSize: 12, fontWeight: 600 }}>
          {task.priority}
        </span>
      </div>
      {task.description && <p style={{ color: "#6b7280", fontSize: 14, margin: "4px 0" }}>{task.description}</p>}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        {nextStatuses.map((s) => (
          <button key={s} onClick={() => onStatusChange(task.id, s)} style={{ fontSize: 12 }}>
            → {STATUS_LABELS[s]}
          </button>
        ))}
      </div>
    </div>
  );
}

function getNextStatuses(current: TaskStatus): TaskStatus[] {
  const transitions: Record<TaskStatus, TaskStatus[]> = {
    TODO: ["IN_PROGRESS", "CANCELLED"],
    IN_PROGRESS: ["IN_REVIEW", "TODO", "CANCELLED"],
    IN_REVIEW: ["IN_PROGRESS", "DONE", "CANCELLED"],
    DONE: [],
    CANCELLED: [],
  };
  return transitions[current] ?? [];
}
