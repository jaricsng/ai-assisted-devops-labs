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

  it("places IN_REVIEW task in the IN_REVIEW column", () => {
    const inReview: Task = { ...tasks[0], id: 4, status: "IN_REVIEW", title: "Task D" };
    render(<KanbanBoard tasks={[inReview]} onStatusChange={vi.fn()} />);
    expect(screen.getByTestId("column-IN_REVIEW")).toHaveTextContent("Task D");
  });

  it("places CANCELLED task in the CANCELLED column", () => {
    const cancelled: Task = { ...tasks[0], id: 5, status: "CANCELLED", title: "Task E" };
    render(<KanbanBoard tasks={[cancelled]} onStatusChange={vi.fn()} />);
    expect(screen.getByTestId("column-CANCELLED")).toHaveTextContent("Task E");
  });

  it("renders all five column headers including Cancelled", () => {
    render(<KanbanBoard tasks={[]} onStatusChange={vi.fn()} />);
    expect(screen.getByText(/Cancelled/)).toBeInTheDocument();
  });
});
