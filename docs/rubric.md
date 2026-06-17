# Assessment Rubric — AI-Assisted DevOps Lab

## Overview

This rubric covers the full 22-module lab (Modules 00–19, plus 05b for observability and 07b for E2E testing). Each criterion is graded on a 4-level scale. Multiply the level score by the criterion weight to get the weighted score for that criterion. Sum all weighted scores to get the final mark.

### Performance Levels

| Level | Score | Description |
|-------|-------|-------------|
| **Distinction** | 4 | Exceeds requirements — demonstrates deep understanding, professional-grade output, and evidence of critical thinking about trade-offs |
| **Merit** | 3 | Meets all requirements with good quality — correct, complete, and showing solid understanding |
| **Pass** | 2 | Meets minimum requirements — functional but may have gaps in quality or understanding |
| **Fail** | 1 | Does not meet minimum requirements — missing, broken, or demonstrating fundamental misunderstanding |

### Grade Boundaries

| Final mark | Grade |
|------------|-------|
| 85–100 | Distinction |
| 70–84 | Merit |
| 50–69 | Pass |
| 0–49 | Fail |

---

## Criteria Summary

| # | Criterion | Weight |
|---|-----------|--------|
| 1 | [Functional Application](#1-functional-application) | 20% |
| 2 | [Code Quality & Architecture](#2-code-quality--architecture) | 15% |
| 3 | [Testing](#3-testing) | 15% |
| 4 | [CI/CD Pipeline](#4-cicd-pipeline) | 15% |
| 5 | [Security Practices](#5-security-practices) | 10% |
| 6 | [DevOps Practices](#6-devops-practices) | 10% |
| 7 | [Documentation](#7-documentation) | 5% |
| 8 | [Peer Collaboration & Code Review](#8-peer-collaboration--code-review) | 5% |
| 9 | [Reflection on AI-Assisted Development](#9-reflection-on-ai-assisted-development) | 5% |
| | **Total** | **100%** |

---

## 1. Functional Application

**Weight: 20%** · Verified by: `docker compose up` then manual test script below

### Grading Test Script

Run these checks against the student's repo:

```bash
BASE=http://localhost:8000

# Health and readiness
curl -s $BASE/health   # → {"status":"ok"}
curl -s $BASE/ready    # → {"status":"ready","db":"ok"}

# Security headers (all 8 must be present)
curl -sI $BASE/health | grep -icE "x-frame-options|x-content-type-options|strict-transport-security|referrer-policy|content-security-policy|cache-control|x-xss-protection|permissions-policy"
# → should output 8

# Register two users
curl -s -X POST $BASE/auth/register -H "Content-Type: application/json" \
  -d '{"email":"alice@test.local","full_name":"Alice","password":"Alice123!"}'

TOKEN=$(curl -s -X POST $BASE/auth/login -H "Content-Type: application/json" \
  -d '{"email":"alice@test.local","password":"Alice123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create project and task
PROJECT=$(curl -s -X POST $BASE/projects -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"Test Project"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

TASK=$(curl -s -X POST $BASE/projects/$PROJECT/tasks \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Test Task","priority":"HIGH"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Valid transition: TODO → IN_PROGRESS
curl -s -X PATCH $BASE/projects/$PROJECT/tasks/$TASK \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"IN_PROGRESS"}'

# Invalid transition: IN_PROGRESS → DONE (must return 422)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH $BASE/projects/$PROJECT/tasks/$TASK \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"DONE"}')
echo "Invalid transition → HTTP $STATUS  (expected 422)"

# Token revocation (Module 14)
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE/auth/logout \
  -H "Authorization: Bearer $TOKEN"            # → 204
curl -s -o /dev/null -w "%{http_code}" $BASE/projects \
  -H "Authorization: Bearer $TOKEN"            # → 401 (token revoked)

# Frontend loads
curl -sf http://localhost:5173 > /dev/null && echo "Frontend: UP" || echo "Frontend: DOWN"
```

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | All three tiers start with `docker compose up`; all test-script checks produce correct HTTP responses; `/ready` returns `{"status":"ready","db":"ok"}`; all 8 security headers (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`, `Content-Security-Policy`, `Cache-Control: no-store`, `Permissions-Policy`) present on every response; frontend displays projects and tasks from the live API; status transition buttons work in the UI; 422 on invalid transition confirmed; `POST /auth/logout` revokes token (subsequent request returns 401); `DELETE /auth/users/me` soft-deletes account |
| **Merit** (3) | All three tiers start; API passes all core CRUD checks including the 422 guard; `/ready` returns 200; security headers present; frontend connects and renders data but may have minor UI gaps |
| **Pass** (2) | API starts and passes core CRUD checks; invalid transition returns 422; security headers may be missing; frontend may not connect to the live API or may be missing significant UI features |
| **Fail** (1) | `docker compose up` fails or crashes; core CRUD operations missing; status transition guard not enforced on the server side; only one or two tiers run |

---

## 2. Code Quality & Architecture

**Weight: 15%** · Verified by: code review of `backend/app/` and `frontend/src/`

Ask Claude Code: `/review-conventions` and `/check-db` to aid grading.

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | Router/Service/Repository boundaries strictly respected — no business logic in routers, no HTTP exceptions in repositories; SQLAlchemy models use `Mapped[]` annotations throughout; all public service functions have docstrings; TypeScript strict mode, no `any`; async/await used consistently in all DB operations; Alembic migrations have both `upgrade` and `downgrade`; no bare `except:` blocks |
| **Merit** (3) | Layer boundaries respected with at most 1–2 minor violations (e.g., a simple validation in a router that should be in the service); models and schemas well-structured; docstrings present on most public functions; TypeScript mostly strict with 1–2 tolerated `any` |
| **Pass** (2) | Three-layer structure exists but boundaries are blurred in places (e.g., HTTPException raised from repository, or DB session used directly in a router); basic type hints present; some functions missing docstrings; TypeScript type coverage partial |
| **Fail** (1) | No clear separation of concerns — business logic mixed with HTTP handling; no type hints or annotations; database access scattered across multiple layers; no Alembic migrations (schema created manually) |

---

## 3. Testing

**Weight: 15%** · Verified by: CI coverage artifact + reading test files

### Coverage Gate (minimum to pass)

Backend: `pytest --cov=app --cov-fail-under=70` must exit 0.
Frontend: `npm test` coverage report must show ≥70% statements.

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | Backend coverage ≥85%; frontend coverage ≥80%; tests verify behaviour (not just line coverage) — each test has a clear Arrange/Act/Assert structure; unit tests cover service-layer business logic (`test_auth_service.py`, `test_task_service.py`); integration tests use `httpx.AsyncClient` + ASGI transport against the real PostgreSQL container (`test_auth_endpoints.py`, `test_projects_integration.py`, `test_tasks_integration.py`); at least one E2E Playwright test covers the full user journey (Module 07b); tests include negative cases (invalid input, wrong credentials, IDOR attempt, invalid transition, revoked token) |
| **Merit** (3) | Backend ≥70% and frontend ≥70%; tests cover the happy path and at least the 422 invalid-transition case; `conftest.py` contains the rate-limit reset `autouse` fixture; E2E tests present but may not cover all flows |
| **Pass** (2) | Backend ≥70% and frontend ≥70% but tests are mechanical (one test per endpoint, no negative cases); coverage achieved mainly through integration tests with no unit tests for business logic |
| **Fail** (1) | Coverage below 70% on either backend or frontend; CI coverage gate fails; tests largely absent or testing only trivial cases (e.g., only the `/health` endpoint) |

---

## 4. CI/CD Pipeline

**Weight: 15%** · Verified by: GitHub Actions tab + `publish.yml`

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | All seven CI jobs pass (`backend`, `frontend`, `security`, `docker-build`, `smoke-test`, `e2e`, `terraform-plan+tfsec`); `docker-build` has `needs: [backend, frontend]`; dependency caching on both jobs; branch protection on `main` requires all jobs to pass; `publish.yml` builds and pushes images to GHCR with SHA tags; GitHub Actions pinned to commit SHAs (Module 14); Trivy image scan step present with `exit-code: 1` on CRITICAL/HIGH; SBOM generated and uploaded as artifact; `cosign verify` step confirms image provenance before deploy; ZAP baseline scan job present (gated by `if: false`); CD `deploy` job uses a GitHub Environment with a named reviewer; post-deploy health check with auto-rollback; `alembic upgrade head` runs before traffic switches (via `release_command` or deploy entrypoint); k6 smoke test runs against the deployed URL |
| **Merit** (3) | All seven CI jobs pass; branch protection configured; `publish.yml` pushes images to GHCR; at least one cloud deploy target activated (Fly.io or AWS/GCP/Azure `if: false` gate removed); Alembic migrations run as part of deploy; health check passes after deploy |
| **Pass** (2) | CI runs and the `backend` and `frontend` jobs pass; `security` or `docker-build` job may fail with known issues documented; CD pipeline exists but may not complete fully (deploy target not configured); images published to GHCR |
| **Fail** (1) | CI does not run or multiple jobs fail on `main`; no CD pipeline or images not published; branch protection not configured |

---

## 5. Security Practices

**Weight: 10%** · Verified by: `./pen-tests/manual-checks.sh` + `/security-scan` + `/compliance-check` output + git history scan

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | All 38 `manual-checks.sh` checks pass (✅ on all OWASP A01–A07 and Module 14 governance items including 8 security headers, 8 IDOR variants, security.txt, Permissions-Policy); OWASP ZAP baseline scan run (`./pen-tests/zap-scan.sh`) with no HIGH/MEDIUM alerts; `/security-scan` shows no HIGH or CRITICAL findings; `/compliance-check` Domains 6 (security runtime) and 7 (governance) both pass; `.secrets.baseline` committed and `detect-secrets` pre-commit hook active; `SECRET_KEY` not in any committed file; `docs/pen-test-report.md` written with CVSS scores for all findings including ZAP results; at least one finding fixed and re-verified; `bandit` is a CI hard gate (no `--exit-zero`); `SecurityHeadersMiddleware` applied to every response (all 8 headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Strict-Transport-Security, Referrer-Policy, Content-Security-Policy, Cache-Control: no-store, Permissions-Policy); `POST /auth/logout` revokes token via JTI; `DELETE /auth/users/me` soft-deletes account; Dependabot configured (`.github/dependabot.yml`); `docs/adr/0003-security-controls.md` documents the JWT/bcrypt/JTI design decisions |
| **Merit** (3) | All `manual-checks.sh` checks pass; no secrets in the current HEAD or recent commits; `/security-scan` shows only LOW findings; `detect-secrets` hook installed; pen test report present with at least 3 findings documented with CVSS scores; security headers middleware present; token revocation working |
| **Pass** (2) | At least 4 of 6 OWASP check categories pass; no obvious secrets in tracked files; basic security (JWT verification, bcrypt) in place; security headers or token revocation may be missing but documented; some findings not yet addressed |
| **Fail** (1) | Critical `manual-checks.sh` failures (JWT alg:none accepted; IDOR allowing cross-user data access); secrets in git history; plaintext password storage; no pen test report |

---

## 6. DevOps Practices

**Weight: 10%** · Verified by: git log, Grafana/Jaeger, load-test output, `/compliance-check`

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | Git log shows ≥15 Conventional Commits across ≥3 feature branches; all PRs used the PR template; observability stack starts (`docker compose --profile observability up`) with all seven containers healthy; Grafana dashboard shows live API metrics and all four alert rules provisioned (`HighErrorRate`, `HighLatency`, `DatabaseUnreachable`, `HighRejectionRate`); Blackbox Exporter probes `/ready` and exposes `probe_success` metric; k6 load test (`load.js`) completed with all thresholds passing; spike test run with token-pool pattern and recovery documented; Locust scenario configured with three user classes (`ReadHeavyUser`, `TaskWriterUser`, `AuthStressUser`); `/compliance-check` run with scorecard included in submission; `docs/adr/` contains ≥5 ADRs covering architecture, API design, security controls, soft-delete strategy, and at least one of: deployment, observability, or rate limiting; Dependabot config committed |
| **Merit** (3) | ≥10 Conventional Commits across ≥2 feature branches; PR template used; observability stack starts and Grafana shows live metrics; k6 smoke test passes and load test attempted; at least 3 ADRs committed |
| **Pass** (2) | ≥8 commits with mostly Conventional Commits format; at least 1 feature branch merged via PR; observability stack configured but Grafana or Prometheus may have gaps; k6 smoke test attempted; at least 1 ADR present |
| **Fail** (1) | Commits directly to `main`; all changes in a single commit or non-descriptive messages; no ADRs; observability not configured; no load tests run |

---

## 7. Documentation

**Weight: 5%** · Verified by: reading `README.md`, `docs/api/openapi.yaml`, `CLAUDE.md`, docstrings

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | `README.md` accurately describes the app, setup steps, and running tests (a new contributor could follow it cold); OpenAPI spec in `docs/api/openapi.yaml` matches all implemented endpoints (`npx swagger-parser validate` exits 0); all public service-layer functions have docstrings; `CLAUDE.md` is project-specific; `CONTRIBUTING.md` describes the branch strategy and PR process; `docs/user-guide.md` covers all user-facing features including observability access; `docs/operations.md` covers start/stop, testing, migrations, and common problems; `docs/pen-test-report.md` documents all findings with CVSS scores; `docs/reflection.md` is substantive and self-critical |
| **Merit** (3) | README is accurate and covers setup; most service functions have docstrings; OpenAPI spec present and mostly accurate; CLAUDE.md updated; pen test report present; at least one of user-guide, operations, or reflection is well-written |
| **Pass** (2) | README exists and covers basic setup; OpenAPI spec may not match implementation; docstrings on some functions; CLAUDE.md is mostly the default template; pen test report may be missing or thin |
| **Fail** (1) | README is the starter scaffold with no student content; no OpenAPI spec or spec is blank; no docstrings; CLAUDE.md not updated |

---

## 8. Peer Collaboration & Code Review

**Weight: 5%** · Verified by: GitHub PR comments on the repo

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | Gave ≥5 substantive PR review comments with specific line references and concrete improvement suggestions; ran `/code-review` and `/security-review` before submitting; responded to all received comments (agreed, disagreed with reasoning, or implemented the fix); review comments show understanding of the codebase (not generic advice) |
| **Merit** (3) | Gave ≥3 substantive PR review comments; responded to received comments; evidence of running `/code-review` (mentions it in a comment or reflection) |
| **Pass** (2) | Gave ≥3 review comments but they are generic ("looks good", "maybe add more tests") rather than specific; received comments were not responded to or were only acknowledged without action |
| **Fail** (1) | Gave fewer than 3 review comments or only "LGTM" comments; did not respond to received review comments; no evidence of running `/code-review` |

---

## 9. Reflection on AI-Assisted Development

**Weight: 5%** · Verified by: reading `docs/reflection.md`

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | 700–900 words; includes ≥3 specific examples of Claude Code prompts used (with the actual prompt and what was produced); includes ≥2 examples of overriding or correcting Claude Code's output and explains the reasoning; includes a load testing insight (what the numbers revealed that manual testing could not); identifies a concrete best practice carried forward with an example from their own code; includes a specific architectural decision they would make differently, cross-referenced to an ADR; demonstrates critical thinking about when AI assistance helps vs hinders |
| **Merit** (3) | 500–700 words; includes ≥2 specific Claude Code examples with prompts; includes ≥1 example of disagreeing with Claude Code; includes a load testing or observability observation; identifies a best practice carried forward |
| **Pass** (2) | 400–600 words; describes Claude Code helping in general terms without specific examples; reflection is largely positive with limited critical engagement; best practice identified but not grounded in a specific codebase example |
| **Fail** (1) | Under 300 words; superficial ("Claude Code was helpful" with no specifics); no example of critical engagement; or not submitted |

---

## Grading Sheet

Copy this template for each student.

```
Student:
Repo URL:
Date graded:

─────────────────────────────────────────────────────────────
CRITERION                              LEVEL   WEIGHT   SCORE
─────────────────────────────────────────────────────────────
1. Functional Application              /4    ×  20%  =
2. Code Quality & Architecture         /4    ×  15%  =
3. Testing                             /4    ×  15%  =
4. CI/CD Pipeline                      /4    ×  15%  =
5. Security Practices                  /4    ×  10%  =
6. DevOps Practices                    /4    ×  10%  =
7. Documentation                       /4    ×   5%  =
8. Peer Collaboration & Code Review    /4    ×   5%  =
9. Reflection                          /4    ×   5%  =
─────────────────────────────────────────────────────────────
TOTAL (max 100)                                        /100
GRADE
─────────────────────────────────────────────────────────────

Notes:
```

### Score calculation

Each level (1–4) maps to a percentage band used for calculating the weighted score:

| Level | % used in calculation |
|-------|----------------------|
| 4 (Distinction) | 100% |
| 3 (Merit) | 80% |
| 2 (Pass) | 60% |
| 1 (Fail) | 30% |

Example: Criterion 1 (Functional Application, weight 20%) at level 3 (Merit) = 0.80 × 20 = **16 points**.

---

## Student Self-Assessment Checklist

Complete this before submission. If any item is not checked, address it or note the reason in your reflection.

### Application
- [ ] `docker compose up` starts all three tiers with no errors
- [ ] `curl http://localhost:8000/ready` returns `{"status":"ready","db":"ok"}`
- [ ] I can register, log in, create a project, and create tasks in the browser
- [ ] TODO → DONE directly returns 422 (business rule enforced server-side)
- [ ] A second user cannot access the first user's projects or tasks (IDOR check)

### Code Quality
- [ ] No business logic in routers; no `HTTPException` in repositories
- [ ] All SQLAlchemy models use `Mapped[]` annotations and include `deleted_at`
- [ ] TypeScript strict mode passes (`npm run typecheck` exits 0)
- [ ] All public service functions have docstrings

### Testing
- [ ] `pytest --cov=app --cov-fail-under=70` passes
- [ ] `npm test` coverage ≥70%
- [ ] Integration tests cover auth endpoints, projects CRUD, tasks CRUD, and IDOR isolation
- [ ] Tests include negative cases (wrong password, IDOR attempt, invalid transition, revoked token)
- [ ] `conftest.py` has the rate-limit reset `autouse` fixture
- [ ] At least one E2E Playwright test covers register → create project → create task

### CI/CD
- [ ] All seven CI jobs pass on my latest push (`backend`, `frontend`, `security`, `docker-build`, `smoke-test`, `e2e`, `terraform-plan+tfsec`)
- [ ] Branch protection requires CI to pass before merging to `main`
- [ ] `publish.yml` pushes images to GHCR on merge to `main`
- [ ] `alembic upgrade head` runs before traffic switches (release command or deploy entrypoint)
- [ ] GitHub Actions steps pinned to commit SHAs (not floating `@v3`-style tags)

### Security
- [ ] `./pen-tests/manual-checks.sh` — all 38 OWASP A01–A07 and Module 14 checks PASS (including 8 IDOR variants, 8 security headers, security.txt, Permissions-Policy)
- [ ] `./pen-tests/zap-scan.sh` — ZAP baseline scan run with no HIGH or MEDIUM alerts
- [ ] `/security-scan` — no HIGH or CRITICAL findings; `bandit` is a hard CI gate (no `--exit-zero`)
- [ ] No secrets in git history (`/check-secrets` clean); `.secrets.baseline` committed
- [ ] Production `SECRET_KEY` is NOT in any committed file
- [ ] `docs/pen-test-report.md` — all findings with CVSS scores, ZAP scan results included
- [ ] All 8 security headers on every API response (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`, `Content-Security-Policy`, `Cache-Control: no-store`, `Permissions-Policy`)
- [ ] `POST /auth/logout` revokes token — subsequent requests return 401
- [ ] `DELETE /auth/users/me` soft-deletes account — login and token both return 401 after deletion
- [ ] Dependabot configured (`.github/dependabot.yml` committed)
- [ ] `docs/adr/0003-security-controls.md` documents JWT/bcrypt/JTI design decisions

### DevOps
- [ ] ≥10 Conventional Commits across ≥2 feature branches
- [ ] At least 5 ADRs in `docs/adr/` (architecture, API design, security controls, soft-delete strategy, deployment — plus observability and/or rate limiting for Distinction)
- [ ] k6 smoke test passes; load test run with all thresholds green
- [ ] Observability stack starts (`--profile observability`) with all seven containers healthy
- [ ] Grafana dashboard shows API metrics; all four alert rules are provisioned
- [ ] Blackbox Exporter probes `/ready` — `probe_success` metric visible in Prometheus

### Documentation
- [ ] README setup steps tested — a clean checkout follows them without extra steps
- [ ] OpenAPI spec validates (`npx swagger-parser validate docs/api/openapi.yaml`)
- [ ] `docs/pen-test-report.md` documents all findings with CVSS scores
- [ ] `docs/user-guide.md` — covers all UI features and the observability section
- [ ] `docs/operations.md` — covers start/stop, tests, migrations, and common problems
- [ ] `docs/reflection.md` — 600+ words with specific Claude Code prompt examples, a load testing insight (Section 6), and an architectural decision cross-referenced to an ADR (Section 8)

### Peer Review
- [ ] Given ≥3 substantive PR review comments with specific line references
- [ ] Responded to all received review comments
