import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { KanbanBoard } from "./KanbanBoard";
import type { Task } from "../api/types";

const tasks: Task[] = [
  { id: 1, project_id: 1, title: "Task A", description: null, status: "TODO", priority: "MEDIUM", assignee_id: null, due_date: null, created_at: "" },
  { id: 2, project_id: 1, title: "Task B", description: null, status: "IN_PROGRESS", priority: "HIGH", assignee_id: null, due_date: null, created_at: "" },
  { id: 3, project_id: 1, title: "Task C", description: null, status: "DONE", priority: "LOW", assignee_id: null, due_date: null, created_at: "" },
];

describe("KanbanBoard", () => {
  it("renders all four column headers", () => {
    render(<KanbanBoard tasks={[]} onStatusChange={vi.fn()} />);
    expect(screen.getByText(/To Do/)).toBeInTheDocument();
    expect(screen.getByText(/In Progress/)).toBeInTheDocument();
    expect(screen.getByText(/In Review/)).toBeInTheDocument();
    expect(screen.getByText(/Done/)).toBeInTheDocument();
  });

  it("places each task in the correct column", () => {
    render(<KanbanBoard tasks={tasks} onStatusChange={vi.fn()} />);
    const todoColumn = screen.getByTestId("column-TODO");
    const inProgressColumn = screen.getByTestId("column-IN_PROGRESS");
    expect(todoColumn).toHaveTextContent("Task A");
    expect(inProgressColumn).toHaveTextContent("Task B");
  });

  it("shows empty state for columns with no tasks", () => {
    render(<KanbanBoard tasks={[]} onStatusChange={vi.fn()} />);
    expect(screen.getAllByText("No tasks").length).toBeGreaterThan(0);
  });
});
