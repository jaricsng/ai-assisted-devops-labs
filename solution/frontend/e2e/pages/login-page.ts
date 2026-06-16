import type { Page } from "@playwright/test";

export class LoginPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto("/login");
  }

  async login(email: string, password: string) {
    await this.page.fill('input[type="email"]', email);
    await this.page.fill('input[type="password"]', password);
    await this.page.click('button[type="submit"]');
  }

  async registerViaApi(email: string, fullName: string, password: string) {
    await this.page.request.post("http://localhost:8000/auth/register", {
      data: { email, full_name: fullName, password },
    });
  }
}
