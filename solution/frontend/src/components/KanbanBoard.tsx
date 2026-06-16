import type { Task, TaskStatus } from "../api/types";
import { TaskCard } from "./TaskCard";

interface Props {
  tasks: Task[];
  onStatusChange: (taskId: number, status: TaskStatus) => void;
}

const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: "TODO", label: "To Do" },
  { status: "IN_PROGRESS", label: "In Progress" },
  { status: "IN_REVIEW", label: "In Review" },
  { status: "DONE", label: "Done" },
  { status: "CANCELLED", label: "Cancelled" },
];

export function KanbanBoard({ tasks, onStatusChange }: Props) {
  return (
    <div data-testid="kanban-board" style={{ display: "flex", gap: 16 }}>
      {COLUMNS.map(({ status, label }) => {
        const columnTasks = tasks.filter((t) => t.status === status);
        return (
          <div key={status} style={{ flex: 1, minWidth: 200 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
              {label} ({columnTasks.length})
            </h3>
            <div data-testid={`column-${status}`}>
              {columnTasks.map((task) => (
                <TaskCard key={task.id} task={task} onStatusChange={onStatusChange} />
              ))}
              {columnTasks.length === 0 && (
                <p style={{ color: "#9ca3af", fontSize: 13 }}>No tasks</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
