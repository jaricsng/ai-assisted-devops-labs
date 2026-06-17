import type { Page } from "@playwright/test";

export class ProjectDetailPage {
  constructor(private page: Page) {}

  column(status: string) {
    return this.page.getByTestId(`column-${status}`);
  }

  async moveTask(currentButtonLabel: string) {
    await Promise.all([
      this.page.waitForResponse(
        (r) => r.url().includes("/tasks/") && r.request().method() === "PATCH"
      ),
      this.page.getByRole("button", { name: currentButtonLabel }).first().click(),
    ]);
  }
}
