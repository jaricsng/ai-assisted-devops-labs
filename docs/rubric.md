# Assessment Rubric — AI-Assisted DevOps Lab

## Overview

This rubric covers the full 13-module lab. Each criterion is graded on a 4-level scale. Multiply the level score by the criterion weight to get the weighted score for that criterion. Sum all weighted scores to get the final mark.

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

# Frontend loads
curl -sf http://localhost:5173 > /dev/null && echo "Frontend: UP" || echo "Frontend: DOWN"
```

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | All three tiers start with `docker compose up`; all 6 test-script checks produce correct HTTP responses; frontend displays projects and tasks from the live API; drag-and-drop or inline status change works in the UI; 422 on invalid transition confirmed both via API and frontend shows the error message |
| **Merit** (3) | All three tiers start; API passes all test-script checks including the 422 guard; frontend connects and renders data but may have minor UI gaps (e.g., missing error message display) |
| **Pass** (2) | API starts and passes core CRUD checks; invalid transition returns 422; frontend may not connect to the live API or may be missing significant UI features |
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
| **Distinction** (4) | Backend coverage ≥85%; frontend coverage ≥80%; tests verify behaviour (not just line coverage) — each test has a clear Arrange/Act/Assert structure; service-layer tests use mocked repositories (not a real DB); integration tests use `httpx.AsyncClient` with a test DB; at least one E2E Playwright test covers the full user journey; tests include negative cases (invalid input, wrong credentials, forbidden access) |
| **Merit** (3) | Backend ≥70% and frontend ≥70%; tests cover the happy path and at least the 422 invalid-transition case; fixtures in `conftest.py` for DB setup/teardown; E2E tests present but may not cover all flows |
| **Pass** (2) | Backend ≥70% and frontend ≥70% but tests are mechanical (one test per endpoint, no negative cases); coverage achieved mainly through integration tests with no unit tests for business logic |
| **Fail** (1) | Coverage below 70% on either backend or frontend; CI coverage gate fails; tests largely absent or testing only trivial cases (e.g., only the `/health` endpoint) |

---

## 4. CI/CD Pipeline

**Weight: 15%** · Verified by: GitHub Actions tab + `publish.yml`

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | All five CI jobs pass (`backend`, `frontend`, `security`, `docker-build`, `smoke-test`); `docker-build` has `needs: [backend, frontend]`; dependency caching added to both `backend` and `frontend` jobs; branch protection on `main` requires all jobs; `publish.yml` builds and pushes images to GHCR with SHA tags; CD `deploy` job uses a GitHub Environment with a named reviewer; post-deploy health check loop with auto-rollback implemented; k6 smoke test runs against the deployed URL; Alembic `release_command` configured in `fly.toml` |
| **Merit** (3) | All four original CI jobs pass; branch protection configured; `publish.yml` pushes images to GHCR; Fly.io deploy job runs and health check passes; Alembic migrations run as release command |
| **Pass** (2) | CI runs and the `backend` and `frontend` jobs pass; `security` or `docker-build` job may fail with known issues documented; CD pipeline exists but may not complete fully (e.g., no Fly.io account set up); images published to GHCR |
| **Fail** (1) | CI does not run or multiple jobs fail on the `main` branch; no CD pipeline or images not published; branch protection not configured |

---

## 5. Security Practices

**Weight: 10%** · Verified by: `./pen-tests/manual-checks.sh` + `/security-scan` output + git history scan

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | All `manual-checks.sh` checks pass (✅ on all OWASP A01–A07 items); `/security-scan` shows no HIGH or CRITICAL findings; git history contains no secrets (`.secrets.baseline` committed; `detect-secrets` pre-commit hook active); production `SECRET_KEY` set via `flyctl secrets set`, not in any committed file; `docs/pen-test-report.md` written with CVSS scores for each finding; at least one finding fixed and re-verified; STRIDE threat model in `docs/adr/`; `bandit --exit-zero` removed and gate hardened |
| **Merit** (3) | All `manual-checks.sh` checks pass; no secrets in the current HEAD or recent commits; `/security-scan` shows only LOW findings; `detect-secrets` hook installed; pen test report present with at least 3 findings documented |
| **Pass** (2) | At least 4 of 6 OWASP check categories pass; no obvious secrets in tracked files; basic security configuration (JWT signature verification, password hashing with bcrypt) in place; some security findings not yet addressed but documented |
| **Fail** (1) | Critical `manual-checks.sh` failures (e.g., JWT alg:none accepted; IDOR allowing cross-user data access); secrets committed to git history; plaintext password storage; no pen test report |

---

## 6. DevOps Practices

**Weight: 10%** · Verified by: git log, Grafana/Jaeger, load-test output

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | Git log shows ≥15 Conventional Commits across ≥3 feature branches; all PRs used the PR template; observability stack starts (`docker compose --profile observability up`) and the Grafana dashboard shows live API metrics; k6 load test (`load.js`) completed with all thresholds passing; spike test run and recovery time documented; Locust scenario configured with three user classes; `docs/adr/` contains ≥3 ADRs (architecture, a tech choice, and one security or performance decision) |
| **Merit** (3) | ≥10 Conventional Commits across ≥2 feature branches; PR template used; observability stack starts and `/metrics` serves Prometheus data; k6 smoke test passes; at least 2 ADRs committed |
| **Pass** (2) | ≥8 commits with mostly Conventional Commits format; at least 1 feature branch merged via PR; observability stack configured but not fully verified; k6 smoke test attempted; 1 ADR present |
| **Fail** (1) | Commits directly to `main`; all changes in a single commit or with non-descriptive messages; no ADRs; observability not configured; no load tests run |

---

## 7. Documentation

**Weight: 5%** · Verified by: reading `README.md`, `docs/api/openapi.yaml`, `CLAUDE.md`, docstrings

### Performance Levels

| Level | Evidence required |
|-------|------------------|
| **Distinction** (4) | `README.md` accurately describes the app, setup steps, and running tests (a new contributor could follow it cold); OpenAPI spec in `docs/api/openapi.yaml` matches all implemented endpoints (run `npx swagger-parser validate`); all public service-layer functions have docstrings; `CLAUDE.md` is project-specific (not the default template); `CONTRIBUTING.md` describes the branch strategy and PR process; `docs/reflection.md` is substantive and self-critical |
| **Merit** (3) | README is accurate and covers setup; most service functions have docstrings; OpenAPI spec present and mostly accurate; CLAUDE.md updated; at least one of CONTRIBUTING.md or reflection.md is well-written |
| **Pass** (2) | README exists and covers the basic setup; OpenAPI spec may not match implementation; docstrings on some but not most functions; CLAUDE.md is mostly the default template |
| **Fail** (1) | README is the starter scaffold with no student-written content; no OpenAPI spec or spec is blank; no docstrings; CLAUDE.md not updated |

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
| **Distinction** (4) | 500–700 words; includes ≥3 specific examples of Claude Code prompts used (with the actual prompt and what was produced); includes ≥2 examples of overriding or correcting Claude Code's output and explains the reasoning; identifies a concrete best practice carried forward with an example from their own code; includes a specific architectural decision they would make differently; demonstrates critical thinking about when AI assistance helps vs hinders |
| **Merit** (3) | 400–600 words; includes ≥2 specific Claude Code examples with prompts; includes ≥1 example of disagreeing with Claude Code; identifies a best practice carried forward |
| **Pass** (2) | 300–500 words; describes Claude Code helping in general terms without specific examples; reflection is largely positive with limited critical engagement; best practice identified but not grounded in a specific codebase example |
| **Fail** (1) | Under 200 words; superficial ("Claude Code was helpful" with no specifics); no example of critical engagement; or not submitted |

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
- [ ] I can register, log in, create a project, and create tasks in the browser
- [ ] TODO → DONE directly returns 422 (business rule enforced server-side)
- [ ] A second user cannot access the first user's projects or tasks

### Code Quality
- [ ] No business logic in routers; no `HTTPException` in repositories
- [ ] All SQLAlchemy models use `Mapped[]` annotations
- [ ] TypeScript strict mode passes (`npm run typecheck` exits 0)
- [ ] All public service functions have docstrings

### Testing
- [ ] `pytest --cov=app --cov-fail-under=70` passes
- [ ] `npm test` coverage ≥70%
- [ ] Tests include negative cases (wrong password, IDOR attempt, invalid transition)
- [ ] At least one E2E Playwright test covers register → create project → create task

### CI/CD
- [ ] All five CI jobs pass on my latest push
- [ ] Branch protection requires CI to pass before merging to `main`
- [ ] `publish.yml` pushes images to GHCR on merge to `main`
- [ ] Alembic `release_command` runs migrations before traffic switches

### Security
- [ ] `./pen-tests/manual-checks.sh` — all checks PASS
- [ ] `/security-scan` — no HIGH or CRITICAL findings
- [ ] No secrets in git history (`/check-secrets` clean)
- [ ] Production `SECRET_KEY` is NOT in any committed file
- [ ] `docs/pen-test-report.md` — at least 3 findings with CVSS scores

### DevOps
- [ ] ≥10 Conventional Commits across ≥2 feature branches
- [ ] At least 2 ADRs in `docs/adr/`
- [ ] k6 smoke test passes (`k6 run load-tests/k6/smoke.js`)
- [ ] Grafana dashboard shows API metrics when observability stack is running

### Documentation
- [ ] README setup steps tested — a clean checkout follows them without extra steps
- [ ] OpenAPI spec validates (`npx swagger-parser validate docs/api/openapi.yaml`)
- [ ] `docs/reflection.md` — 400+ words with specific Claude Code prompt examples

### Peer Review
- [ ] Given ≥3 substantive PR review comments with specific line references
- [ ] Responded to all received review comments
