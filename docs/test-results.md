# Test Results — Task Manager

**Date:** 2026-06-15  
**Branch:** main  
**Run environment:** Docker Compose (Python 3.12-slim, Node 24, PostgreSQL 16)

---

## Backend Unit & Integration Tests

**Runner:** pytest 9.1.0 + pytest-asyncio 1.4.0  
**Command (Docker runner):**
```bash
docker run --rm --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="<test-key>" -e ENVIRONMENT=test -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-report=term-missing -v"
```

| Metric | Result |
|--------|--------|
| Tests collected | 133 |
| Tests passed | **133 ✅** |
| Tests failed | 0 |
| Coverage (total) | **88%** (threshold: 70%) |
| Duration | ~76s |

### Coverage by module

| Module | Coverage |
|--------|----------|
| `app/config.py` | 100% |
| `app/middleware/body_limit.py` | 100% |
| `app/middleware/security_headers.py` | 100% |
| `app/models/*` | 100% |
| `app/schemas/*` | 100% |
| `app/services/auth_service.py` | 100% |
| `app/middleware/logging.py` | 86% |
| `app/middleware/metrics.py` | 84% |
| `app/middleware/rate_limit.py` | 100% |
| `app/services/task_service.py` | 86% |
| `app/database.py` | 92% |
| `app/main.py` | 69% |
| `app/telemetry.py` | 55% |
| **TOTAL** | **88%** |

HTML coverage report: `backend/htmlcov/index.html`

### Test suites

| Suite | Tests | Focus |
|-------|-------|-------|
| `test_auth_service.py` | 7 | Password hashing, JWT encode/decode, JTI revocation |
| `test_task_service.py` | 13 | Status machine transitions (7 cases), task update logic (6 cases including assignee_id, due_date) |
| `test_governance.py` | 29 | Security headers, body size limit, input constraints, rate limit, X-Forwarded-For, sliding window, audit logs (10 events), SECRET_KEY validator |
| `test_auth_endpoints.py` | 11 | Register, login, logout, GDPR delete, token revocation |
| `test_auth_integration.py` | 9 | Weak/empty/invalid password → 422, user enumeration, invalid token, alg:none, expired JWT, missing sub claim |
| `test_security.py` | 9 | Password validator directly, CORS policy, preflight, server header fingerprinting |
| `test_projects_integration.py` | 9 | Project CRUD, IDOR isolation (2 cases) |
| `test_tasks_integration.py` | 23 | Task lifecycle, IDOR (task + comment level, 4 cases), comments, status transitions, task filtering, soft delete, COMMENT_CREATED audit |
| `test_observability.py` | 23 | /health, /ready, /metrics, X-Request-ID, log events, OTel trace injection, unhandled exception handler, telemetry shutdown, security.txt |
| **Total** | **133** | |

---

## Frontend Unit Tests

**Runner:** Vitest 2.1.9 + @vitest/coverage-v8  
**Command:** `npm test -- --run`

| Metric | Result |
|--------|--------|
| Test files | 9 |
| Tests passed | **48 ✅** |
| Tests failed | 0 |
| Statement coverage | **100%** |
| Branch coverage | **96.52%** |
| Duration | ~2.5s |

### Test suites

| Suite | Tests | Focus |
|-------|-------|-------|
| `App.test.tsx` | 3 | Routing, auth redirect |
| `TaskCard.test.tsx` | 9 | Priority badge, status transitions (TODO→IN_PROGRESS, IN_PROGRESS→IN_REVIEW, IN_REVIEW→DONE), cancel button, terminal state |
| `KanbanBoard.test.tsx` | 5 | Column headers, task placement (all 5 statuses), empty state |
| `LoginPage.test.tsx` | 3 | Form render, success flow, error display |
| `ProjectsPage.test.tsx` | 5 | Loading, list, empty state, form submit, empty name guard |
| `ProjectDetailPage.test.tsx` | 6 | Loading, kanban, task create, status update |
| `App.test.tsx` | 4 | Routing, auth redirect, authenticated user sees projects |
| `api/client.test.ts` | 3 | Auth header, no-token case, baseURL |
| `api/projects.test.ts` | 4 | list/get/create/remove |
| `api/tasks.test.ts` | 6 | list/create/update/remove/comments |
| **Total** | **48** | |

---

## E2E Tests (Playwright)

**Runner:** Playwright 1.61.0 (Chromium)  
**Command:** `PLAYWRIGHT_BASE_URL=http://localhost:5173 npx playwright test e2e/ --reporter=list`  
**Prerequisites:** Full Docker Compose stack running (API + DB + frontend)

| Metric | Result |
|--------|--------|
| Tests | 4 |
| Passed | **4 ✅** |
| Failed | 0 |
| Duration | 3.8s |

### Scenarios

| Test | Result |
|------|--------|
| Authentication › user can register and log in | ✅ Pass |
| Authentication › shows error on invalid credentials | ✅ Pass |
| Task flow › user can create a project, add a task, and move it to In Progress | ✅ Pass |
| Task flow › task cannot be moved directly from TODO to DONE | ✅ Pass |

> **Note:** E2E tests must run after any pen test run; the pen test triggers the rate limiter (20 rapid login attempts) which returns 429 for subsequent logins. Restart the API container (`docker compose restart api`) to clear in-memory rate limit state before running E2E.

---

## Load Test — k6 Smoke

**Runner:** k6 (Docker: grafana/k6:latest)  
**Command:** `docker run --rm --network host -e BASE_URL=http://localhost:8000 -v load-tests/k6:/scripts grafana/k6:latest run /scripts/smoke.js`  
**Scenario:** 1 VU, 60s, thresholds: p95 < 1000ms + error rate < 1%

| Metric | Result | Threshold |
|--------|--------|-----------|
| Checks passed | 287 / 287 (100%) | — |
| Error rate | **0.00%** | < 1% ✅ |
| p95 latency | **21.73ms** | < 1000ms ✅ |
| p50 latency | 12.92ms | — |
| p99 latency | — | — |
| RPS | 4.71 req/s | — |
| Iterations | 57 | — |

### Check breakdown

| Check | Result |
|-------|--------|
| setup: register 201 | ✅ |
| setup: login 200 | ✅ |
| health 200 | ✅ |
| create project 201 | ✅ |
| create task 201 | ✅ |
| status transition 200 | ✅ |
| invalid transition 422 | ✅ |

---

## Load Test — k6 Smoke (1 VU, updated)

**Runner:** k6 v2.0.0 (Docker: `grafana/k6`)
**Command:** `docker run --rm --network task-manager_default -e BASE_URL=http://api:8000 -v $(pwd)/load-tests/k6:/scripts grafana/k6 run /scripts/smoke.js`
**Scenario:** 1 VU, 60 s — now includes list_projects and list_tasks checks (9 per-iteration checks + 4 setup + 1 teardown = 14 check types)

| Metric | Result | Threshold |
|--------|--------|-----------|
| Checks passed | 500 / 500 (100%) | — |
| Error rate | **0.00%** | < 1% ✅ |
| p95 latency | **20.32ms** | < 1000ms ✅ |
| p50 latency | 10ms | — |
| Iterations | 55 | — |
| RPS | 8.19 req/s | — |

**Checks:**
`setup: health 200` ✅ · `setup: ready 200` ✅ · `setup: register 201` ✅ · `setup: login 200` ✅ · `health 200` ✅ · `ready 200` ✅ · `list projects 200` ✅ · `create project 201` ✅ · `create task 201` ✅ · `list tasks 200` ✅ · `status transition 200` ✅ · `add comment 201` ✅ · `invalid transition 422` ✅ · `teardown: logout 204` ✅

---

## Load Test — k6 Load (50 VUs)

**Runner:** k6 v2.0.0 (Docker: `grafana/k6`)
**Command:** `docker run --rm --network task-manager_default -e BASE_URL=http://api:8000 -v $(pwd)/load-tests/k6:/scripts grafana/k6 run /scripts/load.js`
**Scenario:** Ramp 0→10 VUs (1 min), 10→50 VUs (2 min), hold 50 VUs (5 min), ramp-down (1 min)
**Date:** 2026-06-16

| Metric | Result | Threshold |
|--------|--------|-----------|
| Checks passed | 34,428 / 34,428 (100%) | — |
| Error rate | **0.00%** | < 1% ✅ |
| p95 latency (overall) | **463.65ms** | < 500ms ✅ |
| p95 latency (list_projects) | **282.58ms** | < 400ms ✅ |
| p95 latency (list_tasks) | **332.04ms** | < 400ms ✅ |
| task_create_duration p95 | **496.14ms** | < 600ms ✅ |
| status_transition_duration p95 | **535.14ms** | < 600ms ✅ |
| comment_duration p95 | **533ms** | < 600ms ✅ |
| Total requests | 34,460 | — |
| RPS | 56.46 req/s | — |
| Iterations | 5,738 | — |

| Metric | avg | med | p90 | p95 |
|--------|-----|-----|-----|-----|
| http_req_duration | 175.68ms | 139.08ms | 376.39ms | 463.65ms |
| list_projects | 111.93ms | 92.03ms | 226.91ms | 282.58ms |
| list_tasks | 127.53ms | 103.91ms | 256.53ms | 332.04ms |
| status_transition | 213.04ms | 183ms | 432ms | 535.14ms |
| comment | 212.24ms | 183ms | 430.3ms | 533ms |
| task_create | 202.25ms | 175ms | 407ms | 496.14ms |

> **Threshold calibration:** Thresholds are set for local Docker at 50 VUs (pool_size=20, max_overflow=30). Cloud deployments with managed PostgreSQL will comfortably beat these numbers.

---

## Penetration Test — Manual Checks

**Script:** `pen-tests/manual-checks.sh http://localhost:8000`  
**Date:** 2026-06-15

| Category | Check | Result |
|----------|-------|--------|
| A01 — Broken Access Control | IDOR: User B cannot read User A's project | ✅ Pass |
| A01 | IDOR: User B cannot delete User A's project | ✅ Pass |
| A01 | IDOR: User B cannot list tasks in User A's project | ✅ Pass |
| A01 | IDOR: User B cannot read User A's task | ✅ Pass |
| A01 | IDOR: User B cannot modify User A's task | ✅ Pass |
| A01 | IDOR: User B cannot delete User A's task | ✅ Pass |
| A01 | IDOR: User B cannot list comments on User A's task | ✅ Pass |
| A01 | IDOR: User B cannot add comment to User A's task | ✅ Pass |
| A01 | Unauthenticated request to /projects returns 401 | ✅ Pass |
| A02 — Cryptographic Failures | JWT alg:none rejected | ✅ Pass |
| A02 | Tampered JWT signature rejected | ✅ Pass |
| A03 — Injection | SQL injection in task title | ✅ Pass |
| A03 | XSS payload in project name | ✅ Pass |
| A04 — Insecure Design | Business rule: TODO→DONE rejected with 422 | ✅ Pass |
| A04 | Terminal state CANCELLED is irreversible (CANCELLED→IN_PROGRESS rejected with 422) | ✅ Pass |
| A04 | Rate limiting active (429 on 11th attempt; max_requests=10, window_seconds=60) | ✅ Pass |
| A04 | No user enumeration (identical error responses) | ✅ Pass |
| A05 — Security Misconfiguration | CORS: API does not reflect arbitrary origins | ✅ Pass |
| A05 | Server header does not disclose versions | ✅ Pass |
| A07 — Auth Failures | Weak password '123' rejected with 422 | ✅ Pass |
| A07 | Empty password rejected with 422 | ✅ Pass |
| Module 14 — Governance | X-Content-Type-Options header present | ✅ Pass |
| Module 14 | X-XSS-Protection header present | ✅ Pass |
| Module 14 | X-Frame-Options header present | ✅ Pass |
| Module 14 | HSTS header present | ✅ Pass |
| Module 14 | Content-Security-Policy header present | ✅ Pass |
| Module 14 | Referrer-Policy header present | ✅ Pass |
| Module 14 | Cache-Control: no-store header present | ✅ Pass |
| Module 14 | Permissions-Policy header present | ✅ Pass |
| Module 14 | security.txt: GET /.well-known/security.txt returns Contact field (RFC 9116) | ✅ Pass |
| Module 14 | /ready returns 200 | ✅ Pass |
| Module 14 | Logout returns 204 | ✅ Pass |
| Module 14 | Revoked token rejected with 401 (JTI revocation) | ✅ Pass |
| Module 14 | GDPR deletion returns 204 | ✅ Pass |
| Module 14 | Soft-deleted user's token rejected with 401 | ✅ Pass |
| Module 14 | Body size limit: Content-Length > 1 MiB returns 413 | ✅ Pass |
| Module 14 | Input validation: project name > 255 chars returns 422 | ✅ Pass |
| Module 14 | Observability: GET /metrics returns 200 | ✅ Pass |

**Summary: 38 PASS, 0 FAIL**

---

## Penetration Test — OWASP ZAP Baseline Scan

**Tool:** OWASP ZAP 2.16.x (Docker: `ghcr.io/zaproxy/zaproxy:stable`)
**Command:** `./pen-tests/zap-scan.sh http://localhost:8000`
**Date:** 2026-06-15
**Scope:** Unauthenticated baseline (passive + light active probes)

| Metric | Result |
|--------|--------|
| URLs crawled | 4 (unauthenticated endpoints only) |
| Passive checks | 66 |
| Alerts — High | 0 |
| Alerts — Medium | 0 |
| Alerts — Low | 0 |
| Alerts — Informational | 1 |

**Finding:** `[INFORMATIONAL] Re-examine Cache-control Directives` — no `Cache-Control` header on initial crawl.

**Resolution:** `Cache-Control: no-store` added to `SecurityHeadersMiddleware` (all subsequent responses confirmed to include the header). Finding resolved.

> **ZAP coverage note:** ZAP baseline crawls only unauthenticated URLs (no session cookie/token). Authenticated endpoints (`/projects`, `/tasks`, `/comments`) are not reachable by the baseline scanner. To include authenticated coverage, run ZAP with `-z "auth..."` passing a Bearer token, or run ZAP full active scan with a pre-authenticated session.

---

## Summary

| Test Suite | Tests / Checks | Pass | Fail | Notes |
|------------|----------------|------|------|-------|
| Backend (pytest) | 133 | 133 | 0 | 88% coverage |
| Frontend (Vitest) | 48 | 48 | 0 | 100% stmts, 96.5% branches |
| E2E (Playwright) | 4 | 4 | 0 | — |
| Load — k6 smoke | 500 checks (55 iters) | 500 | 0 | p95=20ms, 14 check types |
| Load — k6 load | 34,428 checks (5,738 iters) | 34,428 | 0 | 50 VUs, p95=463ms < 500ms |
| Pen test — manual | 38 checks | 38 | 0 | OWASP A01–A07 + 8 headers + IDOR (8 cases) + body limit + input validation + /metrics + security.txt |
| Pen test — ZAP | 66 passive checks | 66 | 0 | 1 info finding resolved |
| **Total** | **497+** | **497+** | **0** | |
