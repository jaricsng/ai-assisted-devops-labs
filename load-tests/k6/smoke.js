/**
 * k6 smoke test — 1 virtual user, 60 seconds.
 *
 * Purpose: verify the API starts correctly and handles a single user without
 * errors before running heavier load scenarios.
 *
 * Run: k6 run load-tests/k6/smoke.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 1,
  duration: "60s",
  setupTimeout: "30s",   // register + login only — no sleep needed
  thresholds: {
    http_req_failed: ["rate<0.01"],       // zero tolerance for errors in smoke
    http_req_duration: ["p(95)<1000"],    // p95 under 1 s (lenient for smoke)
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// setup() runs once before all VUs start — register + login once to avoid
// hitting the /auth/login rate limit (10 req/min per IP) during iterations.
export function setup() {
  // Verify both probes are up before starting the test.
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "setup: health 200": (r) => r.status === 200 });
  const ready = http.get(`${BASE_URL}/ready`);
  check(ready, { "setup: ready 200": (r) => r.status === 200 });

  const email = `smoke_${Date.now()}@example.com`;

  const reg = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, full_name: "k6 Smoke", password: "K6Smoke123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(reg, { "setup: register 201": (r) => r.status === 201 });

  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password: "K6Smoke123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(login, { "setup: login 200": (r) => r.status === 200 });

  return { token: login.json("access_token"), email };
}

export default function ({ token }) {
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // 1. Liveness probe
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health 200": (r) => r.status === 200 });

  // 2. Readiness probe (DB connectivity)
  const ready = http.get(`${BASE_URL}/ready`);
  check(ready, { "ready 200": (r) => r.status === 200 });

  // 3. List projects (authenticated read — exercises owner_id index)
  const projList = http.get(`${BASE_URL}/projects`, { headers });
  check(projList, { "list projects 200": (r) => r.status === 200 });

  // 4. Create project
  const proj = http.post(
    `${BASE_URL}/projects`,
    JSON.stringify({ name: `Smoke Project ${Date.now()}` }),
    { headers }
  );
  check(proj, { "create project 201": (r) => r.status === 201 });
  const projectId = proj.json("id");

  // 5. Create task
  const task = http.post(
    `${BASE_URL}/projects/${projectId}/tasks`,
    JSON.stringify({ title: "Smoke Task", priority: "MEDIUM" }),
    { headers }
  );
  check(task, { "create task 201": (r) => r.status === 201 });
  const taskId = task.json("id");

  // 6. List tasks (FK index read on project_id)
  const taskList = http.get(`${BASE_URL}/projects/${projectId}/tasks`, { headers });
  check(taskList, { "list tasks 200": (r) => r.status === 200 });

  // 7. Advance status TODO → IN_PROGRESS
  const patch = http.patch(
    `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
    JSON.stringify({ status: "IN_PROGRESS" }),
    { headers }
  );
  check(patch, { "status transition 200": (r) => r.status === 200 });

  // 8. Add a comment
  const comment = http.post(
    `${BASE_URL}/projects/${projectId}/tasks/${taskId}/comments`,
    JSON.stringify({ body: "Smoke test comment" }),
    { headers }
  );
  check(comment, { "add comment 201": (r) => r.status === 201 });

  // 9. List comments (verify FK read on task_id)
  const comments = http.get(
    `${BASE_URL}/projects/${projectId}/tasks/${taskId}/comments`,
    { headers }
  );
  check(comments, { "list comments 200": (r) => r.status === 200 });

  // 10. Invalid transition — expect 422 (responseCallback tells k6 not to count this as a failure)
  const bad = http.patch(
    `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
    JSON.stringify({ status: "DONE" }),  // IN_PROGRESS → DONE is invalid
    { headers, responseCallback: http.expectedStatuses(422) }
  );
  check(bad, { "invalid transition 422": (r) => r.status === 422 });

  // 11. RFC 9116 security disclosure endpoint
  const secTxt = http.get(`${BASE_URL}/.well-known/security.txt`);
  check(secTxt, {
    "security.txt 200": (r) => r.status === 200,
    "security.txt has Contact field": (r) => r.body.includes("Contact:"),
  });

  sleep(1);
}

// teardown() runs once after all VUs finish — log out to verify token revocation.
export function teardown({ token }) {
  const r = http.post(
    `${BASE_URL}/auth/logout`,
    null,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  check(r, { "teardown: logout 204": (r) => r.status === 204 });
}
