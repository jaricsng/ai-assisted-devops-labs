import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProjectsPage } from "./ProjectsPage";
import { projectsApi } from "../api/projects";

vi.mock("../api/projects", () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
  },
}));

const mockList = projectsApi.list as ReturnType<typeof vi.fn>;
const mockCreate = projectsApi.create as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProjectsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders project list when loaded", async () => {
    mockList.mockResolvedValue([
      { id: 1, name: "Alpha", description: "First", owner_id: 1, created_at: "" },
      { id: 2, name: "Beta", description: null, owner_id: 1, created_at: "" },
    ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
      expect(screen.getByText("Beta")).toBeInTheDocument();
      expect(screen.getByText("First")).toBeInTheDocument();
    });
  });

  it("shows empty state when no projects", async () => {
    mockList.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No projects yet. Create one above.")).toBeInTheDocument();
    });
  });

  it("calls create API and refreshes list when form is submitted", async () => {
    mockList.mockResolvedValue([]);
    mockCreate.mockResolvedValue({ id: 3, name: "Gamma", owner_id: 1, created_at: "" });
    renderPage();
    await waitFor(() => screen.getByPlaceholderText("New project name"));

    fireEvent.change(screen.getByPlaceholderText("New project name"), { target: { value: "Gamma" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith({ name: "Gamma" });
    });
  });

  it("does not submit empty project name", async () => {
    mockList.mockResolvedValue([]);
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: "Create" }));

    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(mockCreate).not.toHaveBeenCalled();
  });
});
