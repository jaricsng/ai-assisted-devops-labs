import { describe, it, expect, beforeEach, afterEach } from "vitest";
import apiClient from "./client";

describe("apiClient interceptor", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("attaches Authorization header when access_token is in localStorage", async () => {
    localStorage.setItem("access_token", "test-token-abc");
    // The interceptor modifies the config before the request goes out.
    // We verify by checking the interceptor's effect on a request config.
    const config = { headers: { Authorization: "" } } as Parameters<typeof apiClient.interceptors.request["use"]>[0] extends (cfg: infer C) => C ? C : never;

    // Access the eject-able interceptor list via the private property
    const handlers = (apiClient.interceptors.request as unknown as { handlers: Array<{ fulfilled: (c: unknown) => unknown }> }).handlers;
    const interceptor = handlers[0];
    const result = interceptor.fulfilled({ headers: {} as Record<string, string> } as Parameters<typeof interceptor.fulfilled>[0]) as { headers: Record<string, string> };
    expect(result.headers.Authorization).toBe("Bearer test-token-abc");
  });

  it("does not set Authorization header when no token in localStorage", () => {
    const handlers = (apiClient.interceptors.request as unknown as { handlers: Array<{ fulfilled: (c: unknown) => unknown }> }).handlers;
    const interceptor = handlers[0];
    const result = interceptor.fulfilled({ headers: {} as Record<string, string> } as Parameters<typeof interceptor.fulfilled>[0]) as { headers: Record<string, string> };
    expect(result.headers.Authorization).toBeUndefined();
  });

  it("has the correct baseURL from env", () => {
    expect(apiClient.defaults.baseURL).toBeDefined();
  });
});
