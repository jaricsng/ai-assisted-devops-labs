import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProjectDetailPage } from "./ProjectDetailPage";
import { tasksApi } from "../api/tasks";
import type { Task } from "../api/types";

vi.mock("../api/tasks", () => ({
  tasksApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

const mockList = tasksApi.list as ReturnType<typeof vi.fn>;
const mockCreate = tasksApi.create as ReturnType<typeof vi.fn>;
const mockUpdate = tasksApi.update as ReturnType<typeof vi.fn>;

const sampleTasks: Task[] = [
  { id: 1, project_id: 1, title: "Task Alpha", description: null, status: "TODO", priority: "MEDIUM", assignee_id: null, due_date: null, created_at: "" },
  { id: 2, project_id: 1, title: "Task Beta", description: null, status: "IN_PROGRESS", priority: "HIGH", assignee_id: null, due_date: null, created_at: "" },
];

function renderPage(projectId = 1) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProjectDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Loading tasks…")).toBeInTheDocument();
  });

  it("renders kanban board with tasks when loaded", async () => {
    mockList.mockResolvedValue(sampleTasks);
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("kanban-board")).toBeInTheDocument();
      expect(screen.getByText("Task Alpha")).toBeInTheDocument();
      expect(screen.getByText("Task Beta")).toBeInTheDocument();
    });
  });

  it("renders project heading with id", async () => {
    mockList.mockResolvedValue([]);
    renderPage(42);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Project #42" })).toBeInTheDocument();
    });
  });

  it("calls create API when Add Task form is submitted", async () => {
    mockList.mockResolvedValue([]);
    mockCreate.mockResolvedValue({ id: 10, title: "New Task", status: "TODO", priority: "MEDIUM" });
    renderPage();
    await waitFor(() => screen.getByPlaceholderText("New task title"));

    fireEvent.change(screen.getByPlaceholderText("New task title"), { target: { value: "New Task" } });
    fireEvent.click(screen.getByRole("button", { name: "Add Task" }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(1, { title: "New Task" });
    });
  });

  it("calls update API when status change is triggered from kanban", async () => {
    mockList.mockResolvedValue(sampleTasks);
    mockUpdate.mockResolvedValue({ ...sampleTasks[0], status: "IN_PROGRESS" });
    renderPage();
    await waitFor(() => screen.getByText("Task Alpha"));

    fireEvent.click(screen.getByText("→ In Progress"));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(1, 1, { status: "IN_PROGRESS" });
    });
  });

  it("does not submit empty task title", async () => {
    mockList.mockResolvedValue([]);
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: "Add Task" }));

    fireEvent.click(screen.getByRole("button", { name: "Add Task" }));
    expect(mockCreate).not.toHaveBeenCalled();
  });
});
