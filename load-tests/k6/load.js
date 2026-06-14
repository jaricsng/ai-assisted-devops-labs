/**
 * k6 load test — ramp to 50 virtual users, hold for 5 minutes.
 *
 * Purpose: verify the API meets performance SLOs under expected production load.
 * Thresholds define the pass/fail gate — CI can run this as a quality gate.
 *
 * Run: k6 run load-tests/k6/load.js
 * With output: k6 run --out json=results.json load-tests/k6/load.js
 */
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom metrics
const errorRate = new Rate("errors");
const taskCreateDuration = new Trend("task_create_duration", true);
const statusTransitionDuration = new Trend("status_transition_duration", true);

export const options = {
  stages: [
    { duration: "1m", target: 10 },   // ramp up to 10 users
    { duration: "2m", target: 50 },   // ramp up to 50 users
    { duration: "5m", target: 50 },   // hold at 50 users
    { duration: "1m", target: 0 },    // ramp down
  ],
  thresholds: {
    // SLOs — fail the test if these are breached
    http_req_failed:            ["rate<0.01"],   // <1% error rate
    http_req_duration:          ["p(95)<500"],   // p95 < 500 ms
    "http_req_duration{name:list_tasks}": ["p(95)<200"],  // reads faster
    errors:                     ["rate<0.01"],
    task_create_duration:       ["p(95)<600"],
    status_transition_duration: ["p(95)<400"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

function uniqueEmail() {
  return `load_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@k6.local`;
}

function registerAndLogin() {
  const email = uniqueEmail();
  http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, full_name: "k6 User", password: "K6Load123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  const r = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password: "K6Load123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  return r.status === 200 ? r.json("access_token") : null;
}

export function setup() {
  // Verify the API is reachable before starting the load
  const r = http.get(`${BASE_URL}/health`);
  if (r.status !== 200) {
    throw new Error(`API health check failed: ${r.status}`);
  }
}

export default function () {
  const token = registerAndLogin();
  if (!token) {
    errorRate.add(1);
    return;
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  group("read_heavy", () => {
    // List projects (most common operation)
    const projects = http.get(`${BASE_URL}/projects`, { headers, tags: { name: "list_projects" } });
    check(projects, { "list projects 200": (r) => r.status === 200 });
    errorRate.add(projects.status !== 200);
    sleep(0.5);
  });

  group("write_flow", () => {
    // Create project
    const proj = http.post(
      `${BASE_URL}/projects`,
      JSON.stringify({ name: `Load Project ${Date.now()}` }),
      { headers, tags: { name: "create_project" } }
    );
    check(proj, { "create project 201": (r) => r.status === 201 });
    errorRate.add(proj.status !== 201);

    if (proj.status !== 201) return;
    const projectId = proj.json("id");

    // Create task
    const start = Date.now();
    const task = http.post(
      `${BASE_URL}/projects/${projectId}/tasks`,
      JSON.stringify({ title: `Task ${Date.now()}`, priority: "MEDIUM" }),
      { headers, tags: { name: "create_task" } }
    );
    taskCreateDuration.add(Date.now() - start);
    check(task, { "create task 201": (r) => r.status === 201 });
    errorRate.add(task.status !== 201);

    if (task.status !== 201) return;
    const taskId = task.json("id");

    // List tasks in that project
    const list = http.get(
      `${BASE_URL}/projects/${projectId}/tasks`,
      { headers, tags: { name: "list_tasks" } }
    );
    check(list, { "list tasks 200": (r) => r.status === 200 });

    // Status transition
    const txStart = Date.now();
    const tx = http.patch(
      `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
      JSON.stringify({ status: "IN_PROGRESS" }),
      { headers, tags: { name: "status_transition" } }
    );
    statusTransitionDuration.add(Date.now() - txStart);
    check(tx, { "transition 200": (r) => r.status === 200 });
    errorRate.add(tx.status !== 200);

    sleep(1);
  });

  sleep(Math.random() * 2);  // variable think time between 0–2 s
}
