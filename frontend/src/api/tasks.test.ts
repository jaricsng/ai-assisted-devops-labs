import { describe, it, expect, vi, beforeEach } from "vitest";
import { tasksApi } from "./tasks";
import apiClient from "./client";

vi.mock("./client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe("tasksApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("list: calls GET /projects/:id/tasks", async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    const result = await tasksApi.list(1);
    expect(mockClient.get).toHaveBeenCalledWith("/projects/1/tasks");
    expect(result).toEqual([]);
  });

  it("create: calls POST /projects/:id/tasks with payload", async () => {
    const task = { id: 1, title: "T", status: "TODO", priority: "HIGH" };
    mockClient.post.mockResolvedValue({ data: task });
    const result = await tasksApi.create(1, { title: "T", priority: "HIGH" });
    expect(mockClient.post).toHaveBeenCalledWith("/projects/1/tasks", { title: "T", priority: "HIGH" });
    expect(result).toEqual(task);
  });

  it("update: calls PATCH /projects/:pid/tasks/:tid with payload", async () => {
    const updated = { id: 2, status: "IN_PROGRESS" };
    mockClient.patch.mockResolvedValue({ data: updated });
    const result = await tasksApi.update(1, 2, { status: "IN_PROGRESS" });
    expect(mockClient.patch).toHaveBeenCalledWith("/projects/1/tasks/2", { status: "IN_PROGRESS" });
    expect(result).toEqual(updated);
  });

  it("remove: calls DELETE /projects/:pid/tasks/:tid", async () => {
    mockClient.delete.mockResolvedValue({ data: null });
    await tasksApi.remove(1, 3);
    expect(mockClient.delete).toHaveBeenCalledWith("/projects/1/tasks/3");
  });

  it("listComments: calls GET /projects/:pid/tasks/:tid/comments", async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await tasksApi.listComments(1, 2);
    expect(mockClient.get).toHaveBeenCalledWith("/projects/1/tasks/2/comments");
  });

  it("addComment: calls POST /projects/:pid/tasks/:tid/comments with body", async () => {
    const comment = { id: 1, body: "hi" };
    mockClient.post.mockResolvedValue({ data: comment });
    const result = await tasksApi.addComment(1, 2, "hi");
    expect(mockClient.post).toHaveBeenCalledWith("/projects/1/tasks/2/comments", { body: "hi" });
    expect(result).toEqual(comment);
  });
});
