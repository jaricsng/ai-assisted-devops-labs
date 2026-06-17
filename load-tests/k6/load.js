/**
 * k6 load test — ramp to 50 virtual users, hold for 5 minutes.
 *
 * Purpose: verify the API meets performance SLOs under expected production load.
 * Thresholds define the pass/fail gate — CI can run this as a quality gate.
 *
 * Run: k6 run load-tests/k6/load.js
 * With output: k6 run --out json=results.json load-tests/k6/load.js
 *
 * Token pool pattern: logins happen once in setup() so the rate limiter
 * (10 req/min per IP) is never hit during the test iterations. 10 users are
 * pre-created with sleep(7) between each login: 9×7s = 63s — the first login
 * expires from the 60-second sliding window before the 10th fires.
 */
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom per-operation latency trends (ms, percentiles shown in summary).
const errorRate                 = new Rate("errors");
const taskCreateDuration        = new Trend("task_create_duration",        true);
const statusTransitionDuration  = new Trend("status_transition_duration",  true);
const commentDuration           = new Trend("comment_duration",            true);
const commentListDuration       = new Trend("comment_list_duration",       true);

export const options = {
  setupTimeout: "120s",  // 10 users × 7 s = 70 s; allow 50 s headroom
  stages: [
    { duration: "1m", target: 10 },   // ramp up to 10 users
    { duration: "2m", target: 50 },   // ramp up to 50 users
    { duration: "5m", target: 50 },   // hold at 50 users
    { duration: "1m", target: 0 },    // ramp down
  ],
  thresholds: {
    // SLOs — fail the test if any threshold is breached.
    // Calibrated for local Docker at 50 VUs with pool_size=20 connections.
    // Cloud deployments (managed DB, faster storage) should comfortably beat these.
    // NOTE: http_req_duration must use an array to apply multiple constraints —
    //       duplicate JS object keys silently overwrite each other.
    http_req_failed:            ["rate<0.01"],            // <1% overall error rate (strict)
    http_req_duration:          ["p(95)<650", "p(99)<1000"],  // overall: p95 < 650 ms, p99 < 1 s
    "http_req_duration{name:list_tasks}":    ["p(95)<500"],   // indexed FK read
    "http_req_duration{name:list_projects}": ["p(95)<400"],   // indexed owner_id read (faster, no JOIN)
    errors:                     ["rate<0.01"],
    task_create_duration:       ["p(95)<700"],
    status_transition_duration: ["p(95)<750"],  // 2 DB round-trips (GET + PATCH)
    comment_duration:           ["p(95)<750"],  // FK insert + task existence check
    comment_list_duration:      ["p(95)<500"],  // indexed FK read on task_id
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export function setup() {
  // Verify both probes before starting the test
  const health = http.get(`${BASE_URL}/health`);
  if (health.status !== 200) throw new Error(`Health check failed: ${health.status}`);
  const ready = http.get(`${BASE_URL}/ready`);
  if (ready.status !== 200) throw new Error(`Readiness check failed: ${ready.status}`);

  // Pre-create 10 users (≤ rate limit of 10 logins/min) and return their tokens.
  // All VUs share this pool via round-robin — no login requests in the hot path.
  // sleep(7) between logins: 9×7s = 63s means login[0] exits the 60-second
  // sliding window before login[9] fires, staying comfortably under the limit.
  const tokens = [];
  const N = 10;
  for (let i = 0; i < N; i++) {
    const email = `load_${Date.now()}_${i}@example.com`;
    http.post(
      `${BASE_URL}/auth/register`,
      JSON.stringify({ email, full_name: "k6 Load User", password: "K6Load123!" }),
      { headers: { "Content-Type": "application/json" } }
    );
    const r = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email, password: "K6Load123!" }),
      { headers: { "Content-Type": "application/json" } }
    );
    if (r.status === 200) tokens.push(r.json("access_token"));
    if (i < N - 1) sleep(7);  // skip sleep after the last login
  }
  if (tokens.length === 0) throw new Error("setup: all logins failed");
  return { tokens };
}

export default function ({ tokens }) {
  // Rotate through the pre-created token pool — no per-iteration logins.
  const token = tokens[(__VU - 1) % tokens.length];

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  group("read_heavy", () => {
    // List projects (most common operation — read from indexed owner_id column)
    const projects = http.get(
      `${BASE_URL}/projects`,
      { headers, tags: { name: "list_projects" } }
    );
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

    // Create task (track latency separately for bottleneck analysis)
    const tcStart = Date.now();
    const task = http.post(
      `${BASE_URL}/projects/${projectId}/tasks`,
      JSON.stringify({ title: `Task ${Date.now()}`, priority: "MEDIUM" }),
      { headers, tags: { name: "create_task" } }
    );
    taskCreateDuration.add(Date.now() - tcStart);
    check(task, { "create task 201": (r) => r.status === 201 });
    errorRate.add(task.status !== 201);
    if (task.status !== 201) return;
    const taskId = task.json("id");

    // List tasks in that project (exercises FK index on project_id)
    const list = http.get(
      `${BASE_URL}/projects/${projectId}/tasks`,
      { headers, tags: { name: "list_tasks" } }
    );
    check(list, { "list tasks 200": (r) => r.status === 200 });
    errorRate.add(list.status !== 200);

    // Status transition TODO → IN_PROGRESS (2 DB round-trips)
    const txStart = Date.now();
    const tx = http.patch(
      `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
      JSON.stringify({ status: "IN_PROGRESS" }),
      { headers, tags: { name: "status_transition" } }
    );
    statusTransitionDuration.add(Date.now() - txStart);
    check(tx, { "transition 200": (r) => r.status === 200 });
    errorRate.add(tx.status !== 200);

    // Add a comment (exercises comment insert + FK to task)
    const cmStart = Date.now();
    const cm = http.post(
      `${BASE_URL}/projects/${projectId}/tasks/${taskId}/comments`,
      JSON.stringify({ body: "Load test comment" }),
      { headers, tags: { name: "add_comment" } }
    );
    commentDuration.add(Date.now() - cmStart);
    check(cm, { "add comment 201": (r) => r.status === 201 });
    errorRate.add(cm.status !== 201);

    // List comments (FK read on task_id — verifies index under concurrency)
    const clStart = Date.now();
    const cl = http.get(
      `${BASE_URL}/projects/${projectId}/tasks/${taskId}/comments`,
      { headers, tags: { name: "list_comments" } }
    );
    commentListDuration.add(Date.now() - clStart);
    check(cl, { "list comments 200": (r) => r.status === 200 });
    errorRate.add(cl.status !== 200);

    // Get single task by ID (exercises individual row lookup — realistic for
    // detail-view reads that happen alongside list requests)
    const getTask = http.get(
      `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
      { headers, tags: { name: "get_task" } }
    );
    check(getTask, { "get task 200": (r) => r.status === 200 });
    errorRate.add(getTask.status !== 200);

    // Cancel ~10% of tasks to exercise the CANCEL branch (mirrors Locust behaviour).
    // The remaining 90% advance through IN_REVIEW → DONE on 1-in-3 iterations.
    if (Math.random() < 0.10) {
      const rc = http.patch(
        `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
        JSON.stringify({ status: "CANCELLED" }),
        { headers, tags: { name: "cancel_transition" } }
      );
      check(rc, { "cancel transition 200": (r) => r.status === 200 });
      errorRate.add(rc.status !== 200);
    } else if (__ITER % 3 === 0) {
      // Full state machine: IN_PROGRESS → IN_REVIEW → DONE
      const r1 = http.patch(
        `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
        JSON.stringify({ status: "IN_REVIEW" }),
        { headers, tags: { name: "status_transition" } }
      );
      check(r1, { "in_review transition 200": (r) => r.status === 200 });
      errorRate.add(r1.status !== 200);

      if (r1.status === 200) {
        const r2 = http.patch(
          `${BASE_URL}/projects/${projectId}/tasks/${taskId}`,
          JSON.stringify({ status: "DONE" }),
          { headers, tags: { name: "status_transition" } }
        );
        check(r2, { "done transition 200": (r) => r.status === 200 });
        errorRate.add(r2.status !== 200);
      }
    }

    sleep(1);
  });

  sleep(Math.random() * 2);  // variable think time 0–2 s between iterations
}

// teardown() runs once after all VUs finish — revoke all pre-created tokens.
export function teardown({ tokens }) {
  for (const token of tokens) {
    http.post(
      `${BASE_URL}/auth/logout`,
      null,
      { headers: { Authorization: `Bearer ${token}` } }
    );
  }
}
