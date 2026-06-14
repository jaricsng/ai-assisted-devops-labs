# Module 07b — E2E Testing with Playwright

## Learning Objectives

- Understand when E2E tests add value over unit and integration tests
- Install and configure Playwright in the frontend project
- Write E2E tests for the critical user journeys in the Task Manager
- Integrate E2E tests into the CI pipeline
- Use Claude Code to generate and debug Playwright tests

## When to Write E2E Tests

E2E tests launch a real browser, navigate the actual UI, and talk to a running backend and database. They give the highest confidence — but they are also the slowest and most brittle.

**Write E2E tests for flows that must never break:**
- User registration and login
- Creating a project and task (the primary happy path)
- Status transitions via the Kanban board
- Any flow that touches multiple tiers and where a unit or integration test cannot catch the failure

**Do NOT write E2E tests for:**
- UI styling or layout details (a screenshot test or visual review is better)
- Every edge case (unit tests are faster and more focused)
- Flows already covered by integration tests, unless the UI interaction itself is what you're validating

---

## Setup

### 1. Install Playwright

```bash
cd frontend
npm install -D @playwright/test
npx playwright install chromium
```

### 2. Create the Playwright config

Create `frontend/playwright.config.ts`:

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  // Start the full stack before tests run
  webServer: [
    {
      command: "docker compose up api db -d && npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
```

### 3. Create the e2e directory

```bash
mkdir frontend/e2e
```

### 4. Add the test script to package.json

Ask Claude Code:
> "Add an 'e2e' script to frontend/package.json that runs `playwright test`, and an 'e2e:ui' script that runs `playwright test --ui`."

---

## Writing Your First E2E Test

### Test: User Registration and Login

The app has no registration UI — registration is API-only (a deliberate scope decision for the lab). E2E tests call the API directly to create test users, then exercise the login UI. This is the recommended pattern.

Create `frontend/e2e/auth.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Authentication", () => {
  test("user can register and log in", async ({ page }) => {
    // Use both Date.now() and Math.random() to avoid collisions in parallel runs
    const email = `test-${Date.now()}-${Math.floor(Math.random() * 9999)}@example.com`;
    const consoleErrors: string[] = [];
    page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
    page.on("pageerror", (err) => consoleErrors.push(`PAGE ERROR: ${err.message}`));

    // Register via API first (bcrypt is slow — do this before navigating)
    const regRes = await page.request.post("http://localhost:8000/auth/register", {
      data: { email, full_name: "E2E Test User", password: "Password1!" },
    });
    expect(regRes.status()).toBe(201);

    await page.goto("/login");

    // Fill the labeled inputs — id="email" / id="password"
    await page.locator("#email").fill(email);
    await page.locator("#password").fill("Password1!");

    // Click submit and wait for the API response before asserting
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/auth/login") && r.request().method() === "POST"),
      page.click('button[type="submit"]'),
    ]);

    expect(response.status(), `Login API should return 200, errors: ${JSON.stringify(consoleErrors)}`).toBe(200);
    const token = await page.evaluate(() => localStorage.getItem("access_token"));
    expect(token, "Token should be in localStorage after successful login").not.toBeNull();

    await expect(page).toHaveURL("/projects");
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', "nobody@example.com");
    await page.fill('input[type="password"]', "wrongpassword");
    await page.click('button[type="submit"]');
    await expect(page.getByText("Invalid email or password")).toBeVisible();
  });
});
```

Run it:
```bash
cd frontend
npm run e2e
# or with browser visible:
npx playwright test --headed
```

> **Why `page.request.post` for registration?** E2E tests should exercise what users actually do. Since the app provides no registration UI, the test uses the API directly to set up state. The test then validates the login UI, which is what a real user would do. This is the correct pattern — don't add a registration page just so tests can use it.

---

## Activities

### 1. Write the critical user journey test

The most important test: the full flow from login to a task status change.

Ask Claude Code:
> "Write a Playwright E2E test in frontend/e2e/task-flow.spec.ts that:
> 1. Registers a unique user via API (`page.request.post`) and logs in via API to get a token
> 2. Sets the token in localStorage with `page.evaluate`, then navigates to /projects
> 3. Creates a project named 'E2E Test Project'
> 4. Creates a task titled 'My First Task' in that project
> 5. Clicks the '→ In Progress' button on the task card
> 6. Asserts that the task appears in the IN_PROGRESS column
> 7. Asserts that the task no longer appears in the TODO column
> Use page.waitForResponse to wait for the PATCH API call to complete before asserting."

The key pattern for setting up authenticated state without using the UI:
```typescript
async function loginAsNewUser(page: Page): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 9999)}@example.com`;

  const regRes = await page.request.post("http://localhost:8000/auth/register", {
    data: { email, full_name: "E2E User", password: "Password1!" },
  });
  expect(regRes.status()).toBe(201);

  const tokenRes = await page.request.post("http://localhost:8000/auth/login", {
    data: { email, password: "Password1!" },
  });
  const { access_token } = await tokenRes.json();

  // Navigate to /login first to establish the origin, then set localStorage,
  // then navigate to /projects. Going directly to /projects redirects to /login
  // before localStorage can be set.
  await page.goto("/login");
  await page.evaluate((token: string) => localStorage.setItem("access_token", token), access_token);
  await page.goto("/projects");

  return access_token;
}
```

### 2. Use Page Object Model (POM) to reduce duplication

When multiple tests share setup steps (login, create project), extract them into reusable objects.

Ask Claude Code:
> "Create a frontend/e2e/pages/login-page.ts Page Object that encapsulates the login form interaction: a login(email, password) method that fills the form and submits it, and a register(email, fullName, password) method. Show me how to use it in the auth.spec.ts test."

### 3. Use Playwright fixtures for authenticated sessions

Logging in before every test is slow. Playwright can save and reuse browser state (cookies + localStorage).

Ask Claude Code:
> "Show me how to set up a Playwright fixture in frontend/e2e/fixtures.ts that creates a user once, logs in, saves the storage state to a file, and reuses that state across all tests that need authentication. How does this integrate with playwright.config.ts?"

### 4. Test the 422 invalid status transition in the UI

The API returns 422 for invalid transitions. The frontend should show a user-friendly error.

First, check: does the current UI handle this error at all? Open the Kanban board and try to trigger an invalid transition via the browser console:

```javascript
// In browser console (after logging in and navigating to a project with a DONE task):
fetch('/projects/1/tasks/1', {
  method: 'PATCH',
  headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ status: 'TODO' })
}).then(r => r.json()).then(console.log)
```

Ask Claude Code:
> "The frontend currently doesn't handle 422 errors from the status transition API call. Add error handling to the updateStatus mutation in ProjectDetailPage.tsx that shows a toast or alert with the error message from the API response. Then write a Playwright test that mocks the PATCH endpoint to return 422 and verifies the error message appears."

### 5. Add E2E to the CI pipeline

Ask Claude Code:
> "Add a new GitHub Actions job called 'e2e' to .github/workflows/ci.yml that:
> 1. Starts the full stack with `docker compose up -d`
> 2. Waits for the API health check to pass
> 3. Runs `npm run e2e` in the frontend directory
> 4. Uploads the Playwright report as an artifact on failure
> Should this job run on every push or only on PRs to main? Explain the trade-off."

---

## Playwright Debugging Tips

```bash
# Run with browser visible
npx playwright test --headed

# Open interactive UI mode (great for debugging)
npx playwright test --ui

# Run a single test file
npx playwright test e2e/auth.spec.ts

# Show the full trace after a failed test
npx playwright show-report
```

Ask Claude Code when a test is flaky:
> "This Playwright test fails intermittently on CI. Here's the test and the error: [paste]. What are the common causes of flaky Playwright tests and how would you fix this one?"

---

## Unit vs Integration vs Component vs E2E — Quick Reference

| Scenario | Best test type |
|----------|---------------|
| Status transition rule (TODO → DONE blocked) | Unit test (`test_task_service.py`) |
| PATCH /tasks returns 422 for invalid transition | Integration test (`test_tasks_api.py`) |
| TaskCard renders the right transition buttons | Component test (`TaskCard.test.tsx`) |
| User moves a task from TODO to Done in the browser | E2E test (Playwright) |
| Login form shows error on wrong password | Either component test OR E2E (both valid) |

---

## Checkpoint

- [ ] `npx playwright install` completed successfully
- [ ] `frontend/playwright.config.ts` is created and configured
- [ ] `npm run e2e` runs the auth test and passes
- [ ] Critical user journey test (login → project → task → status change) passes
- [ ] Page Object for the login page is implemented
- [ ] E2E job added to `.github/workflows/ci.yml`
- [ ] Commit: `test(e2e): add Playwright setup and critical user journey tests`

## Common Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| Test passes locally, fails in CI | Race condition — API not ready | Use `waitForResponse` or `waitForSelector` instead of `waitForTimeout` |
| Each test creates a new user but emails clash | `Date.now()` collision in parallel runs | Add `Math.random()` or use a UUID |
| Playwright can't find the element | Selector too brittle (class name changes) | Use `getByRole`, `getByLabel`, or `data-testid` attributes |
| Docker Compose not running when E2E starts | `webServer.timeout` too short | Increase timeout or add a health check wait step |
