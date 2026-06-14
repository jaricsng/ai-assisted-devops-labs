import { test, expect } from "@playwright/test";

// NOTE: These tests require the full stack to be running:
//   docker compose up api db -d
//   npm run dev (or use webServer in playwright.config.ts)

test.describe("Authentication", () => {
  test("user can register and log in", async ({ page }) => {
    const email = `test-${Date.now()}-${Math.floor(Math.random() * 9999)}@example.com`;
    const consoleErrors: string[] = [];
    page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
    page.on("pageerror", (err) => consoleErrors.push(`PAGE ERROR: ${err.message}`));

    // Register first (bcrypt is slow — do this before navigating so the user exists)
    const regRes = await page.request.post("http://localhost:8000/auth/register", {
      data: { email, full_name: "E2E Test User", password: "Password1!" },
    });
    expect(regRes.status()).toBe(201);

    await page.goto("/login");

    // Log in via the UI — wait for the API response to confirm the request completed
    await page.locator("#email").fill(email);
    await page.locator("#password").fill("Password1!");
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/auth/login") && r.request().method() === "POST"),
      page.click('button[type="submit"]'),
    ]);

    // Verify API succeeded and token landed in localStorage
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
