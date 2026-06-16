import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TaskCard } from "./TaskCard";
import type { Task } from "../api/types";

const baseTask: Task = {
  id: 1,
  project_id: 1,
  title: "Fix the login bug",
  description: "Users cannot log in on mobile",
  status: "TODO",
  priority: "HIGH",
  assignee_id: null,
  due_date: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("TaskCard", () => {
  it("renders the task title", () => {
    render(<TaskCard task={baseTask} onStatusChange={vi.fn()} />);
    expect(screen.getByText("Fix the login bug")).toBeInTheDocument();
  });

  it("renders the task description", () => {
    render(<TaskCard task={baseTask} onStatusChange={vi.fn()} />);
    expect(screen.getByText("Users cannot log in on mobile")).toBeInTheDocument();
  });

  it("renders the priority badge", () => {
    render(<TaskCard task={baseTask} onStatusChange={vi.fn()} />);
    expect(screen.getByText("HIGH")).toBeInTheDocument();
  });

  it("calls onStatusChange with the correct status when transition button clicked", () => {
    const onStatusChange = vi.fn();
    render(<TaskCard task={baseTask} onStatusChange={onStatusChange} />);
    fireEvent.click(screen.getByText("→ In Progress"));
    expect(onStatusChange).toHaveBeenCalledWith(1, "IN_PROGRESS");
  });

  it("does not show transition buttons for terminal DONE status", () => {
    const task: Task = { ...baseTask, status: "DONE" };
    render(<TaskCard task={task} onStatusChange={vi.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("does not show transition buttons for terminal CANCELLED status", () => {
    const task: Task = { ...baseTask, status: "CANCELLED" };
    render(<TaskCard task={task} onStatusChange={vi.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
