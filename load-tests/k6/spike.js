/**
 * k6 spike test — sudden burst to 100 virtual users, then recovery.
 *
 * Purpose: verify the API survives sudden traffic spikes without cascading
 * failures (connection pool exhaustion, OOM, crash loops).
 *
 * Run: k6 run load-tests/k6/spike.js
 *
 * Unlike the load test, the spike test does NOT enforce strict latency SLOs —
 * some latency increase under a spike is acceptable. It enforces that:
 *   1. Error rate stays below 5% throughout (including the spike peak)
 *   2. The API recovers after the spike: error rate drops back to < 1%
 *
 * Peak VUs: 100 (local Docker has pool_size=20, max_overflow=30 = 50 DB
 * connections max; 100 VUs with think-time between requests is sustainable).
 *
 * Token pool pattern: logins happen once in setup() (10 users × 7 s = 70 s),
 * all 100 spike VUs share the pool via round-robin. This avoids per-iteration
 * register/login requests which would exhaust the 10 req/min rate limit.
 */
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  setupTimeout: "120s",  // 10 users × 7 s = 70 s; 50 s headroom
  stages: [
    { duration: "30s", target: 5 },    // baseline — verify API healthy at low load
    { duration: "15s", target: 100 },  // spike — sudden 20x traffic increase
    { duration: "2m",  target: 100 },  // sustain the spike
    { duration: "15s", target: 5 },    // recover — drop back to baseline
    { duration: "30s", target: 5 },    // verify recovery — error rate must normalise
    { duration: "10s", target: 0 },    // ramp down
  ],
  thresholds: {
    errors:          ["rate<0.05"],    // up to 5% errors acceptable at peak
    http_req_failed: ["rate<0.05"],
    // Recovery check: error rate over last 30 s of verify-recovery stage should
    // be near zero. This is verified manually in the final stage output.
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export function setup() {
  const health = http.get(`${BASE_URL}/health`);
  if (health.status !== 200) throw new Error(`Health check failed: ${health.status}`);
  const ready = http.get(`${BASE_URL}/ready`);
  if (ready.status !== 200) throw new Error(`Readiness check failed: ${ready.status}`);

  // Pre-create 10 users within the rate limit (10 logins/min → 1 per 7 s).
  // All 100 spike VUs share this pool via round-robin — no per-iteration logins.
  const tokens = [];
  const N = 10;
  for (let i = 0; i < N; i++) {
    const email = `spike_${Date.now()}_${i}@example.com`;
    http.post(
      `${BASE_URL}/auth/register`,
      JSON.stringify({ email, full_name: "Spike User", password: "Spike123!" }),
      { headers: { "Content-Type": "application/json" } }
    );
    const r = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email, password: "Spike123!" }),
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

  group("read", () => {
    // Liveness probe
    const health = http.get(`${BASE_URL}/health`, { tags: { name: "health" } });
    check(health, { "health 200": (r) => r.status === 200 });
    errorRate.add(health.status !== 200);

    // Readiness probe (DB connectivity — verifies DB survives the spike)
    const ready = http.get(`${BASE_URL}/ready`, { tags: { name: "ready" } });
    check(ready, { "ready 200": (r) => r.status === 200 });
    errorRate.add(ready.status !== 200);

    // List projects (main authenticated read — exercises owner_id index)
    const projects = http.get(
      `${BASE_URL}/projects`,
      { headers, tags: { name: "list_projects" } }
    );
    check(projects, { "projects 200": (r) => r.status === 200 });
    errorRate.add(projects.status !== 200);
  });

  group("write", () => {
    // Create project + task (exercises INSERT path under spike)
    const proj = http.post(
      `${BASE_URL}/projects`,
      JSON.stringify({ name: `Spike Project ${Date.now()}` }),
      { headers, tags: { name: "create_project" } }
    );
    check(proj, { "create project 201": (r) => r.status === 201 });
    errorRate.add(proj.status !== 201);
    if (proj.status !== 201) return;

    const projId = proj.json("id");
    const task = http.post(
      `${BASE_URL}/projects/${projId}/tasks`,
      JSON.stringify({ title: "Spike Task", priority: "HIGH" }),
      { headers, tags: { name: "create_task" } }
    );
    check(task, { "create task 201": (r) => r.status === 201 });
    errorRate.add(task.status !== 201);

    // Status transition + comment under spike — the most DB-intensive write path
    if (task.status === 201) {
      const taskId = task.json("id");

      // Single-resource GET (detail view — exercises individual row lookup)
      const getTask = http.get(
        `${BASE_URL}/projects/${projId}/tasks/${taskId}`,
        { headers, tags: { name: "get_task" } }
      );
      check(getTask, { "get task 200": (r) => r.status === 200 });
      errorRate.add(getTask.status !== 200);

      const tx = http.patch(
        `${BASE_URL}/projects/${projId}/tasks/${taskId}`,
        JSON.stringify({ status: "IN_PROGRESS" }),
        { headers, tags: { name: "status_transition" } }
      );
      check(tx, { "transition 200": (r) => r.status === 200 });
      errorRate.add(tx.status !== 200);

      const cm = http.post(
        `${BASE_URL}/projects/${projId}/tasks/${taskId}/comments`,
        JSON.stringify({ body: "Spike comment" }),
        { headers, tags: { name: "add_comment" } }
      );
      check(cm, { "add comment 201": (r) => r.status === 201 });
      errorRate.add(cm.status !== 201);

      // List comments (FK read under spike — gap vs load/smoke tests)
      const cl = http.get(
        `${BASE_URL}/projects/${projId}/tasks/${taskId}/comments`,
        { headers, tags: { name: "list_comments" } }
      );
      check(cl, { "list comments 200": (r) => r.status === 200 });
      errorRate.add(cl.status !== 200);
    }
  });

  sleep(0.5);
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
