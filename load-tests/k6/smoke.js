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
import { SharedArray } from "k6/data";

export const options = {
  vus: 1,
  duration: "60s",
  thresholds: {
    http_req_failed: ["rate<0.01"],          // zero tolerance for errors in smoke
    http_req_duration: ["p(95)<1000"],       // p95 under 1 s (lenient for smoke)
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

function uniqueEmail() {
  return `smoke_${Date.now()}_${Math.floor(Math.random() * 9999)}@k6.local`;
}

export default function () {
  // 1. Health check
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health 200": (r) => r.status === 200 });

  // 2. Register
  const email = uniqueEmail();
  const reg = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, full_name: "k6 Smoke", password: "K6Smoke123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(reg, { "register 201": (r) => r.status === 201 });

  // 3. Login
  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password: "K6Smoke123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(login, { "login 200": (r) => r.status === 200 });
  const token = login.json("access_token");

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // 4. Create project
  const proj = http.post(
    `${BASE_URL}/projects`,
    JSON.stringify({ name: "Smoke Project" }),
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

  // 6. Advance status TODO → IN_PROGRESS
  const patch = http.patch(
    `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
    JSON.stringify({ status: "IN_PROGRESS" }),
    { headers }
  );
  check(patch, { "status transition 200": (r) => r.status === 200 });

  // 7. Invalid transition — expect 422
  const bad = http.patch(
    `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
    JSON.stringify({ status: "DONE" }),  // IN_PROGRESS → DONE is invalid
    { headers }
  );
  check(bad, { "invalid transition 422": (r) => r.status === 422 });

  sleep(1);
}
