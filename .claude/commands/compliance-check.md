Run a full best-practice compliance check across all domains: code quality, security (static and runtime), architecture conventions, enterprise governance, observability, documentation completeness, container security, and CI/CD hygiene. Produces a single pass/fail scorecard.

If `$ARGUMENTS` specifies a domain (`code`, `security`, `architecture`, `governance`, `observability`, `docs`, `containers`, `cicd`), run only that domain.
If no argument is given, run all domains and produce the full scorecard.

## Compliance Domains

| # | Domain | What it covers |
|---|--------|---------------|
| 1 | **Code Quality** | Formatting, linting, type safety |
| 2 | **Test Coverage** | Backend ≥70%, frontend ≥70% |
| 3 | **Security SAST** | bandit, detect-secrets, secret pattern grep |
| 4 | **Dependency CVEs** | pip-audit, npm audit |
| 5 | **Security Runtime** | OWASP A01–A07, governance headers, rate limiting |
| 6 | **Architecture** | Layer boundaries, naming, async patterns |
| 7 | **Database** | SQLAlchemy 2.0, Alembic migrations, FK indexes |
| 8 | **Governance** | All 7 security headers, body limit, input validation, audit logs, token revocation, GDPR |
| 9 | **Observability** | /health, /ready, /metrics, structured logging, OTel traces |
| 10 | **Documentation** | README, OpenAPI spec, ADRs, SECURITY.md, CONTRIBUTING.md |
| 11 | **Container Security** | Non-root user, no dev deps in production image |
| 12 | **CI/CD** | All jobs present, security gate, SBOM, image scan |

---

## Domain 1 — Code Quality

Run the Python and TypeScript linters. Report any findings.

```bash
# Python
cd backend
black --check . 2>&1
isort --check . 2>&1
ruff check . 2>&1

# TypeScript
cd ../frontend
npm run typecheck 2>&1
npm run lint 2>&1
```

Grade: ✅ PASS if zero violations in all five tools. ❌ FAIL otherwise — list each violation.

---

## Domain 2 — Test Coverage

Run both test suites and check coverage meets the 70% gate.

```bash
# Backend (via Docker if system Python ≠ 3.12)
docker run --rm --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="test-secret-key-for-local-dev-only" \
  -e ENVIRONMENT=test -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-report=term-missing -q 2>&1"

# Frontend
cd frontend && npm test -- --run 2>&1
```

Grade: ✅ PASS if backend ≥70% AND frontend ≥70%. ❌ FAIL — show which modules are below threshold.

---

## Domain 3 — Security SAST

Run static analysis tools. Never display actual secret values — show only file:line and pattern type.

```bash
# SAST
cd backend && bandit -r app/ -f json -ll 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
for r in results:
    print(f\"[{r['issue_severity']}] {r['filename']}:{r['line_number']} {r['test_id']} {r['issue_text']}\")
print(f'Total: {len(results)} finding(s)')
"

# Secret patterns in tracked files (exclude docs, examples, and test fixtures)
git ls-files | grep -v -E '(\.md$|\.example$|tests/|test_|\.lock$)' | \
  xargs grep -lnE \
    'password\s*=\s*["\x27][^"$\x27\{\}]{6,}|secret[_-]?key\s*=\s*["\x27][^"$\x27\{\}]{8,}|api[_-]?key\s*=\s*["\x27][^"$\x27\{\}]{8,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|BEGIN (RSA |EC )?PRIVATE KEY' \
  2>/dev/null | head -20
```

Grade: ✅ PASS if zero bandit medium+severity findings and zero secret patterns. ❌ FAIL — list each finding with file:line and suggested fix.

---

## Domain 4 — Dependency CVEs

Audit Python and JavaScript packages for known vulnerabilities.

```bash
# Python
cd backend && pip-audit --format json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
vulns = data.get('dependencies', [])
found = [(d['name'], v) for d in vulns for v in d.get('vulns', [])]
for name, v in found:
    print(f\"[{v.get('fix_versions', ['no fix'])[0]}] {name}: {v['id']} — {v['description'][:80]}\")
print(f'Total: {len(found)} CVE(s)')
" 2>/dev/null || echo "pip-audit not installed — run: pip install pip-audit"

# JavaScript
cd ../frontend && npm audit --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
vulns = data.get('vulnerabilities', {})
high_crit = {k: v for k, v in vulns.items() if v.get('severity') in ('high', 'critical')}
for name, v in high_crit.items():
    print(f\"[{v['severity'].upper()}] {name}: {v.get('title', 'unknown')}\")
print(f'High/Critical: {len(high_crit)} package(s)')
" 2>/dev/null
```

Grade: ✅ PASS if zero CVEs found. ❌ FAIL — list affected packages, affected versions, and upgrade path.

---

## Domain 5 — Security Runtime

Run the automated OWASP manual checks. Requires the Docker Compose stack to be running.

```bash
# Check stack is up first
curl -sf http://localhost:8000/health || echo "API not running — start with: docker compose up -d"

chmod +x pen-tests/manual-checks.sh
./pen-tests/manual-checks.sh http://localhost:8000
```

Grade: ✅ PASS if all checks return PASS ✅. ❌ FAIL for any ❌ finding — note the OWASP category and remediation.

If the stack is not running, report Domain 5 as SKIPPED and note the prerequisite.

---

## Domain 6 — Architecture Conventions

Read all files changed since `main` (or all files in scope if no prior `main` branch exists). Check the layer boundaries, naming conventions, and security patterns defined in `CONTRIBUTING.md` and `CLAUDE.md`.

For each Python file in `backend/app/`:

- **Routers** (`routers/`) — must not contain `if` statements on business state, must not call `db.execute()` directly, must not import repository classes directly (only via service)
- **Services** (`services/`) — must not raise `HTTPException` (that belongs in routers), must not call `db.execute()` with raw strings, may call repositories
- **Repositories** (`repositories/`) — must not raise `HTTPException`, must not contain business logic (`if status == ...`), all queries must use SQLAlchemy ORM
- **All Python files** — every function must have type annotations, no bare `except:`, no `eval()`/`exec()` with user input

For each TypeScript file in `frontend/src/`:

- No `any` type
- No inline `fetch()`/`axios()` in components — must go through `src/api/`
- No hardcoded API URLs
- All components must handle loading, error, and success states

Grade: ✅ PASS if no layer boundary violations or type safety issues. ❌ FAIL — show violating file:line and the corrected pattern.

---

## Domain 7 — Database Patterns

Read `backend/app/models/` and `backend/app/repositories/`:

**Models:**
- All use `Mapped[type]` annotations (SQLAlchemy 2.0 style — no legacy `Column()`)
- All foreign key columns have `index=True`
- All models have `id` primary key and `created_at` with `server_default=func.now()`
- Soft-deletable models have `deleted_at: Mapped[datetime | None]`
- All `relationship()` calls specify `back_populates` (not `backref`)

**Repositories:**
- All functions are `async def`
- All `session.execute()` calls are `await`ed
- No `session.commit()` inside repositories
- No f-string SQL — all queries use ORM or `text()` with bound parameters

**Migrations:**
- Any model column added or removed must have a corresponding Alembic migration
- Each migration has `upgrade()` and `downgrade()` implemented

Grade: ✅ PASS if zero violations. ❌ FAIL — show violating file:line and correction.

---

## Domain 8 — Governance

Verify the enterprise governance controls from Module 14 are in place. If the stack is running, verify runtime behaviour; otherwise verify via code inspection.

**Static checks (always):**

Read `backend/app/middleware/security_headers.py` and verify all 7 headers are set:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- `Cache-Control: no-store`

Read `backend/app/middleware/body_limit.py` and verify `MAX_BYTES = 1_048_576`.

Read `backend/app/schemas/` and verify `StringConstraints` are applied to `project.name` (max 255), `task.title` (max 255), `comment.body` (max 5000).

Read `backend/app/services/auth_service.py` and verify `jti` UUID claim is added and a revocation set exists.

Read `backend/app/routers/` and verify every write operation (`POST`, `PATCH`, `DELETE`) emits a `logger.info("audit", action=..., resource=..., resource_id=...)` event.

**Runtime checks (if stack is running):**

```bash
# All 7 headers present
curl -sI http://localhost:8000/health | grep -iE "x-content|x-frame|strict-transport|referrer|content-security|cache-control"

# Body size limit
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/auth/register \
  -H "Content-Length: 1048577" -H "Content-Type: application/json" -d '{}'
# expected: 413

# Token revocation
TOKEN=$(curl -sf -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "%{http_code}" -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/logout
# expected: 204
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8000/projects
# expected: 401
```

Grade: ✅ PASS if all 7 headers present, body limit enforced, token revocation working, all write routes have audit logs. ❌ FAIL — list each missing control.

---

## Domain 9 — Observability

**Static checks:**

Read `backend/app/telemetry.py` and verify:
- `FastAPIInstrumentor` is called
- `SQLAlchemyInstrumentor` is called
- OTLP exporter is configured for traces
- Prometheus metrics middleware is mounted at `/metrics`

Read `backend/app/middleware/logging.py` and verify:
- `request_started` and `request_finished` events are emitted per request
- `method`, `path`, `status_code`, and `duration_ms` fields are bound
- `trace_id` and `span_id` from OTel context are injected into log events

**Runtime checks (if stack is running):**

```bash
curl -sf http://localhost:8000/health    # must return {"status":"ok"}
curl -sf http://localhost:8000/ready     # must return 200 when DB is reachable
curl -sfL http://localhost:8000/metrics  # must return Prometheus text format (contains "# HELP")
```

Grade: ✅ PASS if all three probes respond correctly and telemetry setup is complete. ❌ FAIL — show which probe failed or which telemetry wiring is missing.

---

## Domain 10 — Documentation

Check that required documentation files exist and are non-empty:

```bash
for f in \
  README.md \
  CONTRIBUTING.md \
  SECURITY.md \
  CODE_OF_CONDUCT.md \
  CLAUDE.md \
  docs/api/openapi.yaml \
  docs/adr/0001-architecture.md \
  docs/operations.md \
  docs/user-guide.md; do
  if [ -s "$f" ]; then
    echo "✅ $f"
  else
    echo "❌ $f — missing or empty"
  fi
done
```

Also verify the OpenAPI spec is internally consistent with the implemented routes:
- Read `docs/api/openapi.yaml` and list every `operationId`
- Read `backend/app/routers/` and list every route decorator
- Flag any endpoint in the code that is not in the spec, or vice versa

Grade: ✅ PASS if all required files exist and the OpenAPI spec matches the implementation. ❌ FAIL — list missing files and spec/code drift.

---

## Domain 11 — Container Security

Read `backend/Dockerfile` and `frontend/Dockerfile`:

**Non-root user:**
- `backend/Dockerfile` must contain `RUN useradd` (or `adduser`) and `USER appuser` (or equivalent non-root name)
- `frontend/Dockerfile` must contain `USER` directive with a non-root user

**Production image hygiene:**
- `backend/Dockerfile` must install `"."` not `".[dev]"` in the production stage (dev tools like bandit, pytest, pip-audit should NOT be in the production image)
- No `COPY . .` that would include `.env` or test files — verify `.dockerignore` exists and excludes `.env`, `tests/`, `htmlcov/`

**No hardcoded secrets:**
- No `ENV SECRET_KEY=` with a real value in any Dockerfile
- All secrets injected via environment variables at runtime

Grade: ✅ PASS if both Dockerfiles use non-root users and production image excludes dev deps. ❌ FAIL — show the Dockerfile line and the corrected pattern.

---

## Domain 12 — CI/CD

Read `.github/workflows/ci.yml` and `.github/workflows/publish.yml`:

**CI pipeline must include:**
- `backend` job: black, isort, ruff, pytest with coverage gate
- `frontend` job: tsc, eslint, vitest with coverage gate
- `security` job: bandit (non-zero exit on medium+ findings), pip-audit, npm audit, secret grep
- `docker-build` job: `docker compose build`
- `e2e` job: Playwright tests on PRs to main

**CD pipeline must include:**
- Build and push to GHCR
- Trivy image scan (CRITICAL/HIGH block)
- SBOM generation (anchore/sbom-action)
- Deploy job with health check post-deploy

Grade: ✅ PASS if all 5 CI jobs are present and CD pipeline includes Trivy + SBOM. ❌ FAIL — list missing jobs or missing steps.

---

## Final Scorecard

After running all domains, produce this report:

```
╔══════════════════════════════════════════════════════════════════╗
║  Best-Practice Compliance — Task Manager                         ║
║  Date: YYYY-MM-DD                                                ║
╚══════════════════════════════════════════════════════════════════╝

Domain  1 — Code Quality        ✅ / ❌   [brief result]
Domain  2 — Test Coverage       ✅ / ❌   backend NN%  frontend NN%
Domain  3 — Security SAST       ✅ / ❌   N bandit findings  N secrets
Domain  4 — Dependency CVEs     ✅ / ❌   N Python CVEs  N npm CVEs
Domain  5 — Security Runtime    ✅ / ❌   N/N OWASP checks passed
Domain  6 — Architecture        ✅ / ❌   N files reviewed  N violations
Domain  7 — Database Patterns   ✅ / ❌   N models  N repositories  N violations
Domain  8 — Governance          ✅ / ❌   N/7 headers  body limit  audit logs
Domain  9 — Observability       ✅ / ❌   /health  /ready  /metrics  OTel
Domain 10 — Documentation       ✅ / ❌   N/N required files  OpenAPI drift: N
Domain 11 — Container Security  ✅ / ❌   non-root backend  non-root frontend
Domain 12 — CI/CD               ✅ / ❌   N/5 CI jobs  Trivy  SBOM

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Compliance Score: N/12 domains passing
  Status: ✅ PRODUCTION READY  /  ❌ N domain(s) require remediation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌ domain, produce a remediation block:

```
REMEDIATION — Domain N: <Domain Name>
──────────────────────────────────────
Finding:   <specific issue>
File:      <file>:<line> (if applicable)
Fix:       <exact code change or command>
Effort:    Low / Medium / High
Blocks:    Production deploy? Yes / No
```

Offer to fix any ❌ finding immediately if the code path is clear.

---

## Context

- Most domains can run without the stack (`docker compose up -d` is only needed for Domain 5 and the runtime checks in Domain 8 and 9)
- If `docker compose up -d` is required but the stack is not running, mark runtime sub-checks as SKIPPED and note the prerequisite — do not fail the domain solely on skipped runtime checks
- The security runtime checks in Domain 5 fire 20 rapid login attempts. If you need to run E2E tests afterward, restart the API first: `docker compose restart api`
- Domain 3 (SAST) requires `bandit` and `pip-audit` to be installed: `pip install -e ".[dev]"` from `backend/`
- CLAUDE.md lists the authoritative conventions; CONTRIBUTING.md lists the code standards; both are the source of truth for Domains 1, 6, and 7
