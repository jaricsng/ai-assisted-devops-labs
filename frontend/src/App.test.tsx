import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { App } from "./App";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  );
}

describe("App routing", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("redirects unauthenticated user from /projects to /login", () => {
    localStorage.removeItem("access_token");
    renderAt("/projects");
    expect(screen.getByRole("heading", { name: "Task Manager" })).toBeInTheDocument();
  });

  it("redirects unknown routes to /projects (then /login if unauthenticated)", () => {
    localStorage.removeItem("access_token");
    renderAt("/unknown-route");
    // Redirected to /projects → then /login
    expect(screen.getByRole("heading", { name: "Task Manager" })).toBeInTheDocument();
  });

  it("renders login page at /login", () => {
    renderAt("/login");
    expect(screen.getByRole("heading", { name: "Task Manager" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });
});
