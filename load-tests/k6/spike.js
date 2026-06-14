/**
 * k6 spike test — sudden burst to 200 virtual users, then back down.
 *
 * Purpose: verify the API survives sudden traffic spikes without cascading
 * failures (connection pool exhaustion, OOM, crash loops).
 *
 * Run: k6 run load-tests/k6/spike.js
 *
 * Unlike the load test, the spike test does NOT enforce strict SLOs on latency
 * — some latency increase under a spike is acceptable. It only enforces that
 * the error rate stays below 5% and the API recovers after the spike.
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

export const options = {
  stages: [
    { duration: "30s", target: 5 },    // baseline — verify API is healthy
    { duration: "10s", target: 200 },  // spike — sudden 40x traffic increase
    { duration: "3m",  target: 200 },  // hold — sustain the spike
    { duration: "10s", target: 5 },    // recover — drop back to baseline
    { duration: "30s", target: 5 },    // verify recovery — check error rate normalises
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    errors:          ["rate<0.05"],   // up to 5% errors acceptable during spike peak
    http_req_failed: ["rate<0.05"],
    // No latency threshold — spike tests accept higher latency
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

function uniqueEmail() {
  return `spike_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@k6.local`;
}

export default function () {
  // Spike test uses a lightweight read + auth flow to maximise concurrency
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health 200": (r) => r.status === 200 });
  errorRate.add(health.status !== 200);

  const email = uniqueEmail();
  const reg = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, full_name: "Spike User", password: "Spike123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  errorRate.add(reg.status !== 201);

  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password: "Spike123!" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(login, { "login 200": (r) => r.status === 200 });
  errorRate.add(login.status !== 200);

  if (login.status === 200) {
    const token = login.json("access_token");
    const projects = http.get(`${BASE_URL}/projects`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    check(projects, { "projects 200": (r) => r.status === 200 });
    errorRate.add(projects.status !== 200);
  }

  sleep(0.5);
}
