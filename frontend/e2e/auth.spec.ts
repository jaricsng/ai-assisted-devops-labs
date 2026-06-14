import { test, expect } from "@playwright/test";

// NOTE: These tests require the full stack to be running:
//   docker compose up api db -d
//   npm run dev (or use webServer in playwright.config.ts)

test.describe("Authentication", () => {
  test("user can register and log in", async ({ page }) => {
    const email = `test-${Date.now()}-${Math.floor(Math.random() * 9999)}@example.com`;

    await page.goto("/login");

    // Registration — students add a /register page or form in Module 6
    // For now, register via the API directly and then test the login form
    await page.request.post("http://localhost:8000/auth/register", {
      data: { email, full_name: "E2E Test User", password: "password123" },
    });

    // Log in via the UI
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', "password123");
    await page.click('button[type="submit"]');

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
