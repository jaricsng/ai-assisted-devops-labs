# Instructor Guide

## Lab Overview

This is a self-paced, **22-module lab** (Modules 00–19, plus 05b for observability and 07b for E2E testing). Students build a production-quality three-tier Task Manager using Claude Code at every step of the delivery lifecycle. The lab works for mixed skill levels — beginners will follow the instructions closely while advanced students should be encouraged to deviate, experiment, and extend.

**Estimated time:** 60–105 hours depending on student background.

| Module group | Approximate time | Notes |
|-------------|-----------------|-------|
| Modules 00–05 (setup → business logic) | 8–15 h | Core tier implementation |
| Modules 05b, 06, 07, 07b (observability, frontend, testing, E2E) | 10–15 h | — |
| Modules 08–10 (docs, CI/CD, review) | 6–10 h | — |
| Modules 11–12 (load testing, pen testing) | 6–10 h | — |
| Modules 13–14 (CD, enterprise governance) | 8–14 h | — |
| Modules 15–17 (SLOs, multi-environment, IaC) | 10–16 h | Requires cloud infra + GitHub configuration |
| Modules 18–19 (incident response, threat modeling) | 6–10 h | Covers Operate + Security lifecycle gaps |

---

## Before the Lab Starts

1. **Fork the starter repo** and push to your institution's GitHub org so students fork from there
2. **Set GitHub branch protection** on `main`: require 1 PR review + CI passing
3. **Create student pairings** for Module 10 peer review (do this before the lab, not after)
4. **Pre-seed a demo walkthrough** — run Module 0 yourself and record a 5-minute video showing the working app
5. **Warn students about Docker pull times** — ZAP (~1.5 GB) and k6 pull on first use; pull in advance:
   ```bash
   docker pull ghcr.io/zaproxy/zaproxy:stable
   docker pull grafana/k6
   ```

---

## Common Student Pitfalls

| Problem | Root cause | Solution |
|---------|-----------|---------|
| `docker compose up` fails immediately | Docker Desktop not running | Check Docker status; restart Docker |
| `SECRET_KEY` missing error | `.env` not created from `.env.example` | `cp .env.example .env` and set a real key |
| pytest fails to import `aiosqlite` | Dev dependencies not installed | `pip install -e ".[dev]"` |
| Pre-commit blocks every commit | Black auto-formats the file, student doesn't re-stage | After black runs, `git add` the file again and commit |
| CI fails on coverage | Student wrote feature code without tests | Show them `htmlcov/index.html` to find uncovered lines |
| 422 on status transition in tests | Test doesn't follow the valid transition path | Walk through `VALID_TRANSITIONS` in `task_service.py` |
| `flyctl deploy` auth error in CI | `FLY_API_TOKEN` secret not set or expired | Re-run `flyctl auth token` and update the GitHub secret |
| Frontend 404 on page refresh after deploy | nginx missing `try_files` directive | Add `try_files $uri $uri/ /index.html;` to nginx location block |
| Migration fails during deploy | Backward-incompatible migration | Use expand/contract pattern (Module 13 Activity 6) |
| GHCR push denied in CI | `packages: write` permission not set on the job | Add `permissions: packages: write` to the publish job |
| **`POST /auth/register` returns 422** | Password doesn't meet policy (8+ chars, uppercase, digit) | All example passwords must satisfy the validator, e.g. `"Demo1234!"` not `"password123"` |
| **Unit tests get 429 after ~10 login tests** | Rate-limiter bucket bleeds across tests (all ASGI requests share `"unknown"` IP) | Add `autouse` fixture in `conftest.py` calling `reset_for_testing()` from `app.middleware.rate_limit` |
| **k6 spike/load test exits code 100 in setup** | `setupTimeout` default (60 s) too short for pre-creating 10 users at 7 s/login (63 s total) | Verify `setupTimeout: "120s"` is in the `options` object — the provided scripts include it; custom scripts need it added |
| **k6 load test shows 32%+ errors at 50+ VUs** | Per-iteration `register → login` exhausts the rate limit immediately | Move auth to `setup()`: pre-create N users, return token array; VUs pick by `(__VU - 1) % tokens.length` |
| **DB pool exhaustion under heavy load** | Default `pool_size=5` + `max_overflow=10` insufficient at 50 VUs | Set `pool_size=20, max_overflow=30` in `create_async_engine` |
| **JTI revocation lost on restart** | In-memory `_revoked_jtis` set is process-scoped | Expected limitation; documented in ADR 0003 — production requires Redis |
| Grafana shows "No data" | OTEL_ENABLED=false or Prometheus not scraping | Set `OTEL_ENABLED=true`; verify http://localhost:9090/targets shows API as UP |
| `DatabaseUnreachable` alert never fires | Blackbox Exporter not running | Start with `--profile observability`; check http://localhost:9115/metrics |

---

## Assessment Grading Notes

The full grading rubric is at [`docs/rubric.md`](rubric.md). It defines 9 criteria with 4 performance levels each.

### Quick verification commands

```bash
# Criterion 1 — functional application
docker compose up -d
curl http://localhost:8000/health   # {"status":"ok"}
curl http://localhost:8000/ready    # {"status":"ready","db":"ok"}
curl http://localhost:5173           # React UI loads

# Criterion 3 — test coverage (Docker runner guarantees Python 3.12 + dev deps)
docker run --rm --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="test-secret-key-for-local-dev-only" \
  -e ENVIRONMENT=test -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-fail-under=70 --cov-report=term-missing"
cd frontend && npm test -- --coverage

# Criterion 5 — security checks (38 checks: OWASP A01–A07 + Module 14 governance)
./pen-tests/manual-checks.sh http://localhost:8000

# Criterion 5 — security headers
curl -sI http://localhost:8000/health | grep -E "x-frame|x-content|strict-transport"

# Criterion 5 — token revocation
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"   # must be 204
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/projects \
  -H "Authorization: Bearer $TOKEN"   # must be 401
```

### Common grading pitfalls

- **Coverage number ≠ test quality.** A student can reach 70% by testing only the happy path. Check that negative cases exist (wrong password, forbidden access, invalid transition). If all tests are integration tests with no unit tests, note it in feedback.
- **Layer boundary violations are subtle.** Use `/review-conventions` to surface them — it flags `HTTPException` in repositories and business logic in routers with specific file and line references.
- **Reflection depth varies widely.** The Pass level requires specifics ("I used this prompt: ..."). Vague positivity ("Claude Code was very helpful") is a Fail for criterion 9 regardless of word count.
- **Security: distinguish missing vs broken.** Rate limiting absent = informational finding (document in ADR). IDOR present (User B can read User A's data) = HIGH severity and a criterion 5 fail unless fixed.
- **Module 14 completeness.** All three phases must be present: (1) security headers verified by pen test, (2) JTI revocation tested with a real logout + replay, (3) GDPR soft delete verified in the DB with `deleted_at` set. Supply-chain: Dependabot config committed and bandit runs without `--exit-zero`.

---

## Extension Exercises (for advanced students)

1. **Add task search** — implement `GET /projects/{id}/tasks?status=TODO&priority=HIGH` (spec already written in Module 2)
2. **Email notifications** — when a task is assigned, send an email via `fastapi-mail`
3. **Pagination** — add cursor-based pagination to the task list endpoint
4. **Redis-backed token revocation** — replace the in-memory `_revoked_jtis` set with Redis using `aioredis`; document the trade-offs vs the in-memory approach in ADR 0003
5. **Full ZAP active scan** — run `./pen-tests/zap-scan.sh http://localhost:8000 full` against a disposable DB instance and add any HIGH/MEDIUM findings to the pen test report
6. **Staging environment** — extend the CD pipeline with a staging environment that auto-deploys on every `main` merge; production requires an additional manual promotion step
7. **Load SLO in CI** — add the k6 smoke test as a GitHub Actions step (Module 11 Activity 6 instructions); fail the PR if any threshold is breached
8. **Cloud deploy** — activate one cloud target in `publish.yml` by removing `if: false` from the relevant deploy job and configuring the matching GitHub Environment + secrets (AWS ECS, GCP Cloud Run, or Azure Container Apps — see `docs/adr/0005-deployment-strategy.md`)
9. **Supply-chain attestation** — extend `publish.yml` to sign images with `cosign sign` (keyless Sigstore) and enforce `cosign verify` as a deploy gate; combine with `slsa-github-generator` for SLSA Level 3 provenance (see Module 13 Activity 10 and ADR 0005 §Supply chain hardening)

---

## How to Extend the Lab

To add a new module:
1. Create `docs/modules/NN-topic.md` following the existing module format
2. Update the module table in `README.md`
3. If the module requires new starter code, add it to the scaffold

The lab is designed so each module is independently completable — students who get stuck on one module can skip ahead and return later.

---

## Claude Code Skills Used in This Lab

### Built-in Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/init` | 0, 8 | Generate/update CLAUDE.md |
| `/update-config` | 3 | Configure pre-commit hook |
| `/code-review` | 10 | Peer review |
| `/code-review --comment` | 10 | Post review comments to GitHub PR |

### Project Skills (`.claude/commands/`)

These custom skills are defined in the lab repo and are available the moment students clone it.

#### Coding Standards Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/check-python` | 3, 5, 7 | Run black/isort/ruff — read-only report with explanations |
| `/fix-python [file]` | 3, 5 | Auto-apply black, isort, ruff --fix |
| `/check-frontend` | 6, 7 | Run tsc + ESLint — read-only report with explanations |
| `/fix-frontend [file]` | 6 | Auto-apply ESLint --fix; explain remaining manual fixes |
| `/check-standards` | 9, 10 | Full pre-merge gate: all linters + both test suites + Docker build |
| `/review-conventions` | 5, 7, 10 | AI review of layer boundaries, security, naming, git hygiene |
| `/check-db` | 4, 5 | Review SQLAlchemy models, Alembic migrations, repository patterns |

#### Security Skills (Shift-Left)

| Skill | Module | Purpose |
|-------|--------|---------|
| `/security-scan` | 5, 10, 14 | Automated scan: bandit SAST + pip-audit + npm audit + secret patterns. Risk-ranked report. |
| `/security-review` | 5, 10, 14 | AI OWASP Top 10 review mapped to this codebase. Finds logic-level issues tools miss. |
| `/check-secrets` | 3, 5 | Detect hardcoded credentials in tracked files and git history; verify .gitignore coverage. |
| `/check-dependencies` | 6, 9, 14 | CVE audit for Python + JS packages; checks lock file hygiene, Dependabot config, and CI gap. |
| `/threat-model [feature]` | 1, 5 | STRIDE threat model for the app or a named feature. Produces a prioritised mitigation backlog. |

**Teaching tip — shift-left security:** Introduce `/check-secrets` in Module 3 (before the first real commit) and `/security-scan` in Module 5 (after auth is implemented). Run `/threat-model` in Module 1 as a design exercise before any code is written — this is the shift-left principle in action.

**Teaching tip — peer review:** Have students run `/security-review` on their own PR before the peer reviewer does. Students who find and fix issues themselves demonstrate deeper understanding than those who wait for the reviewer.

#### Compliance Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/compliance-check [domain]` | 14, 15, 16 | Full 12-domain compliance gate: code quality, test coverage, SAST, CVEs, security runtime, architecture, database patterns, governance headers, observability, documentation, container security, CI/CD. Pass a domain name to scope to one area; no arg runs all 12 and produces a scorecard. |

**Teaching tip — Module 14 (Enterprise Governance):** Run `/compliance-check` at the start of Module 14 to establish a baseline scorecard, and again at the end to show what improved. The scorecard format gives students a concrete measure of progress across all 12 domains rather than just the security controls they implemented in that module. Domain 7 (Governance) specifically checks the 8 security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, CSP, Cache-Control, Permissions-Policy), body size limit, and input validation — useful for grading criterion 5 without manual inspection.

**Teaching tip — compliance domains for grading:** `/compliance-check` does not replace the pen test (`manual-checks.sh`) but complements it — the pen test verifies *runtime* behaviour (actual HTTP responses), while the compliance check verifies *code and config* state (middleware registered, Dependabot configured, ADRs present). Use both when grading.

#### Performance & Security Testing Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/load-test [smoke\|load\|spike\|locust]` | 11 | Run k6 or Locust scenario; parse results; correlate with Prometheus/Jaeger |
| `/pen-test [authentication\|access-control\|injection\|design]` | 12 | Automated pen test — manual checks + ZAP scan + OWASP findings report |

**Teaching tip — Module 11 (Load Testing):** Encourage students to use `/load-test smoke` first as a sanity check — a failing smoke test means a broken API, not a performance problem. Then run `/load-test load` while Grafana is open so students can see the dashboard update in real time as VUs ramp up.

**Teaching tip — spike test design:** If students write per-iteration `register → login` in the k6 `default()` function, the rate limiter fires within seconds at 100 VUs and they'll see 30%+ errors. The correct pattern (pre-create N users in `setup()`, share token array across VUs) is documented in `load-tests/k6/spike.js` and Module 11 Activity 5. Use this as a teaching moment: the rate limiter is working correctly — the test design was wrong.

**Teaching tip — Module 12 (Pen Testing):** Emphasise the authorization notice. Students must only test `http://localhost:8000`. The `/pen-test` skill runs automated checks and offers to run ZAP — but the most valuable learning comes from reading the source code to understand *why* a check passed or failed, not just reading the PASS/FAIL output. The `manual-checks.sh` script now includes Module 14 governance checks (security headers, logout/revocation, GDPR deletion) so students see how compliance controls are validated programmatically.

**Common Module 11 pitfall:** k6 not installed. Offer students the Docker alternative (requires `docker compose up -d`; `--network host` is unreliable on macOS Docker Desktop):
```bash
docker run --rm --network task-manager_default \
  -e BASE_URL=http://api:8000 \
  -v "$(pwd)/load-tests/k6:/scripts" \
  grafana/k6 run /scripts/smoke.js
```

**Common Module 12 pitfall:** ZAP Docker pull takes 5+ minutes on first run. Warn students to pull in advance:
```bash
docker pull ghcr.io/zaproxy/zaproxy:stable
```

#### Deployment & Cloud Skills

| Skill | Module | Purpose |
|-------|--------|---------|
| `/check-aspire [file]` | 13 | Review .NET Aspire AppHost wiring, secret hygiene, and manifest readiness |
| `/check-azure [file]` | 13 | Review Azure Container Apps config, OIDC auth, Key Vault, scaling |
| `/check-aws [file]` | 13 | Review ECS Fargate task defs, IAM least-privilege, Secrets Manager, OIDC |
| `/check-gcp [file]` | 13 | Review Cloud Run YAMLs, Workload Identity, Secret Manager, Cloud SQL proxy |

**Teaching tip — Module 13 (Continuous Deployment):** The cloud deploy jobs in `publish.yml` are all gated by `if: false`. This is intentional — students must consciously choose a cloud target, configure GitHub Secrets and Environments, and remove the gate for that specific job. `.NET Aspire` is the recommended local orchestration path (single command starts all services + the Developer Dashboard at https://localhost:15888). For CD, students choose one cloud target: Fly.io (free tier), AWS ECS Fargate, GCP Cloud Run, or Azure Container Apps — all four paths are wired up, each gated by `if: false`. See ADR 0005 for the multi-cloud rationale.

**Teaching tip — secrets management:** Stress that no credentials should appear in committed files. Use `/check-secrets` before every PR merge. The `detect-secrets` pre-commit hook will block commits containing credential patterns, but it must be initialised (`detect-secrets scan > .secrets.baseline`) — help students who skip Module 3 setup.

#### Module 14 Teaching Notes

Module 14 covers five concerns across three phases: transport security, identity controls, and supply chain. The most common student mistake is implementing security headers in the router (adding them to individual response objects) rather than as middleware applied to every response. Use `/review-conventions` to catch this.

The JTI revocation trade-off (in-memory vs Redis) is a deliberate design choice documented in ADR 0003. Students should understand the limitation (revocations lost on restart, not shared across replicas) and be able to articulate when they would accept this trade-off vs when they would reach for Redis. This is excellent material for the Module 10 peer review discussion.

**Common Module 14 pitfalls:**

| Problem | Root cause | Solution |
|---------|-----------|---------|
| Security headers appear on some responses but not all | Headers added in router, not middleware | Move to `SecurityHeadersMiddleware.dispatch()` which wraps every response |
| Audit log missing `user_id` | `user_id` not bound to structlog context | `deps.py:get_current_user` must call `structlog.contextvars.bind_contextvars(user_id=...)` |
| GDPR deletion returns 204 but login still works | Soft delete sets `deleted_at` but auth query doesn't filter it | `user_repository.get_by_email()` must include `WHERE deleted_at IS NULL` |
| Bandit fails CI with B105 false positive | `"secret-key"` config key name looks like a hardcoded secret | Add `# nosec B105` with a comment explaining it's a config key, not a credential |

---

## Lab Scope Boundaries

The following DevSecOps topics are **intentionally out of scope** for this lab. They require infrastructure, tooling, or organisational context beyond what a self-contained lab can provide. If advanced students ask about them, use the table below to frame *why* they are out of scope and *where to learn more*.

| Topic | Why out of scope | Where to learn more |
|-------|-----------------|---------------------|
| **Chaos engineering** (Gremlin, Chaos Monkey, LitmusChaos) | Requires a live multi-node cluster; designed for ops teams operating at scale, not individual developer education | [Principles of Chaos Engineering](https://principlesofchaos.org/), LitmusChaos docs |
| **SIEM / runtime behavioral monitoring** (Falco, Datadog, Splunk) | Enterprise tooling; requires agent deployment, tuned detection rules, and a security operations team to triage alerts | Falco CNCF project, Datadog Cloud SIEM docs |
| **Policy as code** (OPA Rego, Sentinel, Checkov policies) | Kubernetes admission controller concern; OPA is relevant when running workloads on K8s, not Cloud Run or Fly.io | Open Policy Agent docs, `conftest` for Terraform policies |
| **Fuzzing / property-based testing** (Atheris, Hypothesis) | Advanced testing technique; complements but does not replace the pytest suite in this lab. | Hypothesis Python docs, Google OSS-Fuzz |
| **Accessibility (a11y) testing** (Axe, WAVE) | UX / WCAG concern; the lab delivers a JSON API with a thin React UI — not the target of a11y gates | Axe-core, `cypress-axe` plugin |
| **mTLS / certificate pinning** | Network layer handled by cloud load balancers and service meshes (Istio, Linkerd); not applicable to this app-layer stack | Istio docs, SPIFFE/SPIRE for workload identity |

**Teaching guidance:** These topics make excellent **extension exercises** for advanced students (see Extension Exercises section above). Frame them as "the next layer up" in the maturity model — the lab covers everything from code to deploy to operate; these topics extend into *advanced threat detection*, *chaos resilience*, and *infrastructure policy*. None of them would change the grade rubric for this lab.
