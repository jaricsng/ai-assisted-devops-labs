import { describe, it, expect, vi, beforeEach } from "vitest";
import { projectsApi } from "./projects";
import apiClient from "./client";

vi.mock("./client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe("projectsApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("list: calls GET /projects and returns data", async () => {
    const projects = [{ id: 1, name: "Proj", owner_id: 1, created_at: "" }];
    mockClient.get.mockResolvedValue({ data: projects });
    const result = await projectsApi.list();
    expect(mockClient.get).toHaveBeenCalledWith("/projects");
    expect(result).toEqual(projects);
  });

  it("get: calls GET /projects/:id and returns data", async () => {
    const project = { id: 5, name: "P", owner_id: 1, created_at: "" };
    mockClient.get.mockResolvedValue({ data: project });
    const result = await projectsApi.get(5);
    expect(mockClient.get).toHaveBeenCalledWith("/projects/5");
    expect(result).toEqual(project);
  });

  it("create: calls POST /projects with payload and returns data", async () => {
    const project = { id: 2, name: "New", owner_id: 1, created_at: "" };
    mockClient.post.mockResolvedValue({ data: project });
    const result = await projectsApi.create({ name: "New", description: "Desc" });
    expect(mockClient.post).toHaveBeenCalledWith("/projects", { name: "New", description: "Desc" });
    expect(result).toEqual(project);
  });

  it("remove: calls DELETE /projects/:id", async () => {
    mockClient.delete.mockResolvedValue({ data: null });
    await projectsApi.remove(3);
    expect(mockClient.delete).toHaveBeenCalledWith("/projects/3");
  });
});
