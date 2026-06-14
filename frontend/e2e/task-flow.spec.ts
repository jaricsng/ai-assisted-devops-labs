import { test, expect } from "@playwright/test";

// Helper: register + login, returns the token (used for API setup calls)
async function loginAsNewUser(page: import("@playwright/test").Page): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 9999)}@example.com`;

  const regRes = await page.request.post("http://localhost:8000/auth/register", {
    data: { email, full_name: "E2E User", password: "Password1!" },
  });
  expect(regRes.status()).toBe(201);

  const tokenRes = await page.request.post("http://localhost:8000/auth/login", {
    data: { email, password: "Password1!" },
  });
  const { access_token } = await tokenRes.json();

  // Set the token in localStorage then navigate — goto /login first to establish
  // the correct origin, then set localStorage, then navigate to /projects.
  // (Navigating directly to /projects redirects to /login via React Router's
  // <Navigate replace> before we can set localStorage, so reload lands on /login.)
  await page.goto("/login");
  await page.evaluate((token: string) => localStorage.setItem("access_token", token), access_token);
  await page.goto("/projects");

  return access_token;
}

test.describe("Task flow — critical user journey", () => {
  test("user can create a project, add a task, and move it to In Progress", async ({ page }) => {
    await loginAsNewUser(page);

    // Verify we're on the projects page
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();

    // Create a project
    await page.fill('input[placeholder="New project name"]', "E2E Test Project");
    await page.click('button[type="submit"]');

    // Navigate into the project
    await page.click("text=E2E Test Project");
    await expect(page.getByTestId("kanban-board")).toBeVisible();

    // Create a task
    await page.fill('input[placeholder="New task title"]', "My First E2E Task");
    await page.click('button[type="submit"]');

    // Verify the task appears in the TODO column
    const todoColumn = page.getByTestId("column-TODO");
    await expect(todoColumn.getByText("My First E2E Task")).toBeVisible();

    // Move the task to In Progress
    const moveButton = page.getByRole("button", { name: "→ In Progress" }).first();
    await Promise.all([
      page.waitForResponse((r) => r.url().includes("/tasks/") && r.request().method() === "PATCH"),
      moveButton.click(),
    ]);

    // Verify the task moved to the IN_PROGRESS column
    const inProgressColumn = page.getByTestId("column-IN_PROGRESS");
    await expect(inProgressColumn.getByText("My First E2E Task")).toBeVisible();

    // Verify it's gone from TODO
    await expect(todoColumn.getByText("My First E2E Task")).not.toBeVisible();
  });

  test("task cannot be moved directly from TODO to DONE", async ({ page }) => {
    // This tests that the business rule is enforced at the API level
    // The UI doesn't show a "→ Done" button from TODO, so we test via direct API call
    const token = await loginAsNewUser(page);

    const projectRes = await page.request.post("http://localhost:8000/projects", {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: "Transition Test Project" },
    });
    const project = await projectRes.json();

    const taskRes = await page.request.post(`http://localhost:8000/projects/${project.id}/tasks`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { title: "Transition Test Task" },
    });
    const task = await taskRes.json();

    // Attempt invalid transition: TODO → DONE
    const patchRes = await page.request.patch(
      `http://localhost:8000/projects/${project.id}/tasks/${task.id}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { status: "DONE" },
      }
    );

    expect(patchRes.status()).toBe(422);
    const body = await patchRes.json();
    expect(body.detail).toContain("TODO");
  });
});
