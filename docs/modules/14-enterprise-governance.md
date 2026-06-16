# Module 14 — Enterprise Governance & Compliance

## Learning Objectives

- Understand what "enterprise readiness" means for a web API beyond functional correctness
- Apply security hardening in four phases: transport, identity, supply chain, and access control governance
- Implement GDPR-compliant account deletion using soft deletes
- Understand the trade-offs behind in-memory vs distributed token revocation
- Read structured audit logs and correlate them with observability data
- Create a `CODEOWNERS` file that enforces mandatory review on security-sensitive code paths
- Expose a `/.well-known/security.txt` endpoint for responsible vulnerability disclosure
- Use Claude Code to audit an existing codebase against enterprise security standards

---

## Background

A working API is not automatically an enterprise-ready API. Enterprise governance covers:

| Concern | What it means |
|---------|--------------|
| **Transport security** | HTTP security headers, CORS policy, request size limits |
| **Identity & session** | JWT revocation, password policy, GDPR erasure |
| **Audit trail** | Structured logs for every write operation with user attribution |
| **Supply chain** | Automated dependency updates, SAST as a hard CI gate, SBOM generation |
| **Soft deletes** | Data retention for compliance — no hard deletes |

This module implements all five concerns in three phases.

---

## Phase 1 — Transport Security

### 1a. HTTP security headers

Enterprise security scanners and compliance frameworks (SOC 2, PCI-DSS) require standard HTTP security headers on every response. The `SecurityHeadersMiddleware` in `backend/app/middleware/security_headers.py` adds these automatically:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing attacks |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter for older browsers |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforces HTTPS for 1 year |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Restricts content sources |
| `Cache-Control` | `no-store` | Prevents sensitive responses being cached by proxies/browsers |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disables browser feature APIs not used by this API |

**Activity:** Verify all 8 headers are present on every response:

```bash
curl -sI http://localhost:8000/health | grep -E "x-frame|x-content|strict-transport|referrer|cache-control|permissions-policy"
```

All eight should appear. Ask Claude Code:
> "Why is `Content-Security-Policy: default-src 'none'` appropriate for a REST API but would break a web application that serves HTML?"

### 1b. Request body size limit

The `MaxBodySizeMiddleware` rejects any request with a `Content-Length` header exceeding 1 MiB (1,048,576 bytes). This prevents memory exhaustion via oversized payloads.

```bash
# Simulate an oversized request
curl -X POST http://localhost:8000/projects \
  -H "Content-Length: 2000000" \
  -H "Authorization: Bearer $TOKEN"
# Expected: 413 Request Entity Too Large
```

### 1c. Input length constraints

All Pydantic request schemas use `StringConstraints` to enforce maximum lengths:

| Field | Constraint |
|-------|-----------|
| `name` (project, task) | max 255 chars |
| `description` | max 2000 chars |
| `comment.body` | max 5000 chars |
| `full_name` (user) | max 255 chars |

Ask Claude Code:
> "Look at backend/app/schemas/project.py. Are the StringConstraints imported and applied correctly? What HTTP status code does FastAPI return when a constraint is violated?"

---

## Phase 2 — Identity & Audit Controls

### 2a. JWT JTI claim and token revocation

Every JWT now includes a `jti` (JWT ID) claim — a UUID unique to that token issuance. When a user logs out, the JTI is recorded in an in-memory revocation set. Any subsequent request using the same token is rejected with 401.

**Try it:**

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Use the token — should work
curl -s http://localhost:8000/projects -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Log out — revokes the JTI
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
# Expected: 204

# Same token is now rejected
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/projects \
  -H "Authorization: Bearer $TOKEN"
# Expected: 401
```

Ask Claude Code:
> "Read backend/app/services/auth_service.py. The revocation set is in-memory. What happens to the revocation list when the API container restarts? What are the consequences for users who had active sessions?"

> "What would need to change to make token revocation work across multiple API replicas? Sketch the Redis-backed implementation."

> **Production note:** The `SECRET_KEY` used to sign JWTs must be rotated periodically and immediately after a suspected leak. See [`docs/runbooks/runbook-secret-rotation.md`](../runbooks/runbook-secret-rotation.md) for the dual-key rotation procedure that avoids logging out all users simultaneously.

### 2b. Structured audit logging

Every write operation emits a structured audit log event:

```python
logger.info("audit", action="PROJECT_CREATED", resource="project", resource_id=project.id)
```

The `user_id` is automatically bound to the structlog context by `RequestLoggingMiddleware` after the `current_user` dependency resolves it.

The complete set of auditable events emitted by the API:

| Action | Emitted by | Event trigger |
|--------|-----------|---------------|
| `REGISTER` | `POST /auth/register` | New user created |
| `LOGIN_SUCCESS` | `POST /auth/login` | Valid credentials |
| `LOGIN_FAILED` | `POST /auth/login` | Invalid credentials (security event) |
| `LOGOUT` | `POST /auth/logout` | JTI revoked |
| `USER_DELETED` | `DELETE /auth/users/me` | GDPR soft-delete |
| `PROJECT_CREATED` | `POST /projects` | New project |
| `PROJECT_DELETED` | `DELETE /projects/{id}` | Soft-delete |
| `TASK_CREATED` | `POST /projects/{id}/tasks` | New task |
| `TASK_UPDATED` | `PATCH /projects/{id}/tasks/{id}` | Field or status update |
| `TASK_DELETED` | `DELETE /projects/{id}/tasks/{id}` | Soft-delete |
| `COMMENT_CREATED` | `POST /projects/{id}/tasks/{id}/comments` | New comment |

**Verify:**

```bash
# Create a project and watch the audit log
curl -s -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Audit Test Project"}' | python3 -m json.tool

docker compose logs --tail=10 api | jq 'select(.event=="audit")'
# Should show: {"event":"audit","action":"PROJECT_CREATED","resource":"project","resource_id":N,"user_id":N}
```

Ask Claude Code:
> "Which write operations in the codebase emit audit events? Which ones are missing? Look at backend/app/routers/ for any write endpoints without a `logger.info('audit', ...)` call."

All 11 audit event types are verified by `tests/test_governance.py` using `structlog.testing.capture_logs()`:
```bash
pytest tests/test_governance.py -v -k "audit_log"
```

### 2c. Soft deletes and GDPR account deletion

All four domain model tables (`users`, `projects`, `tasks`, `comments`) have a `deleted_at TIMESTAMPTZ` column. When a record is "deleted", the application sets `deleted_at = now(UTC)` rather than issuing a SQL `DELETE`.

**Why soft deletes?**

- Audit trail: records of what was deleted and when
- Recovery: accidental deletes can be reversed by clearing `deleted_at`
- GDPR compliance: user data can be retained for legal hold while making the account inaccessible

**GDPR account deletion:**

```bash
# Delete your account
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/auth/users/me \
  -H "Authorization: Bearer $TOKEN"
# Expected: 204

# Verify: login with the same credentials fails
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234!"}'
# Expected: 401

# Verify in the DB: deleted_at is set
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT id, email, deleted_at FROM users WHERE deleted_at IS NOT NULL;"
```

Ask Claude Code:
> "Read docs/adr/0004-soft-delete-strategy.md. What is the legal rationale for retaining soft-deleted user data? At what point should it be hard-purged?"

---

## Phase 3 — Supply Chain Governance

### 3a. Bandit as a hard CI gate

The `security` CI job runs `bandit -r app/ -c pyproject.toml -ll`. The `-ll` flag means **medium-and-above severity** findings cause a non-zero exit, failing the build.

**Run locally:**

```bash
cd backend && bandit -r app/ -c pyproject.toml -ll
```

For each finding, either fix the code or add a targeted suppression:

```python
# nosec B105 — this is a config key name, not a hardcoded password
SECRET_KEY_SETTING = "secret-key"
```

Ask Claude Code:
> "Run bandit against backend/app/ and explain each finding. For each one, decide: is this a false positive that should be suppressed, or a real issue that needs to be fixed?"

### 3b. Dependabot automated dependency updates

`.github/dependabot.yml` opens weekly PRs for pip, npm, and GitHub Actions updates. This is automated dependency hygiene — catching CVEs in dependencies before they accumulate.

**Activity:** Navigate to your GitHub repo's **Pull requests** tab. If a Dependabot PR is open:
1. Read the PR description and check the changelog
2. Verify CI passes on the PR
3. Approve and merge

Ask Claude Code:
> "What is the difference between a Dependabot security update and a Dependabot version update? Which should be merged immediately and which can wait?"

---

## Phase 4 — Access Control Governance

### 4a. CODEOWNERS for security-sensitive paths

CODEOWNERS ensures that changes to security-critical code cannot merge without a review from a designated owner. This is a process control that complements the technical controls in Phases 1–3.

If you haven't done this in Module 3, create `.github/CODEOWNERS` now. The paths that matter most from a security perspective:

```
# Security middleware — any change here affects every request
backend/app/middleware/               @YOUR_GITHUB_USERNAME

# Auth: JWT signing, bcrypt, JTI revocation
backend/app/routers/auth.py           @YOUR_GITHUB_USERNAME
backend/app/services/auth_service.py  @YOUR_GITHUB_USERNAME
backend/app/routers/deps.py           @YOUR_GITHUB_USERNAME

# Database migrations: irreversible without a rollback plan
backend/alembic/                      @YOUR_GITHUB_USERNAME

# CI/CD pipelines: can execute arbitrary code in GitHub Actions runners
.github/workflows/                    @YOUR_GITHUB_USERNAME

# Security policy and pen test scripts
SECURITY.md                           @YOUR_GITHUB_USERNAME
pen-tests/                            @YOUR_GITHUB_USERNAME
```

Enable enforcement in GitHub: **Settings → Branches → main rule → Require review from Code Owners**.

Ask Claude Code:
> "Review `.github/CODEOWNERS`. The file grants the same single owner to all paths. In a real team, how would you split ownership? Which paths would a security engineer own vs. a platform engineer vs. the application team? What happens when the code owner is on vacation?"

### 4b. Add a `security.txt` disclosure policy

`security.txt` is a standardised file (RFC 9116) that tells security researchers where to report vulnerabilities in your application. Without it, researchers who find a bug have no clear channel and may resort to public disclosure.

Create `backend/app/well_known.py` and wire a route for `GET /.well-known/security.txt`:

```python
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

SECURITY_TXT = """\
Contact: mailto:security@example.com
Expires: 2027-01-01T00:00:00.000Z
Preferred-Languages: en
Policy: https://github.com/YOUR_USERNAME/task-manager/blob/main/SECURITY.md
"""

@router.get("/.well-known/security.txt", response_class=PlainTextResponse, include_in_schema=False)
async def security_txt() -> str:
    return SECURITY_TXT
```

Register the router in `backend/app/main.py`:
```python
from app.well_known import router as well_known_router
app.include_router(well_known_router)
```

Verify:
```bash
curl http://localhost:8000/.well-known/security.txt
```

Update `SECURITY.md` to reference this endpoint so researchers know where to look.

Ask Claude Code:
> "RFC 9116 specifies that the `Expires` field is required and the file must be served over HTTPS. This API is served over HTTP locally. Is there a security concern with serving `security.txt` over HTTP? What does HSTS have to do with this?"

---

## Verification Checklist

Run these checks in order to verify all three phases:

```bash
# Phase 1: Transport
curl -sI http://localhost:8000/health | grep -c "x-frame\|x-content\|strict-transport\|referrer"
# Expected: 4

# Phase 2: Token revocation
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
# Expected: 204
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/projects \
  -H "Authorization: Bearer $TOKEN"
# Expected: 401

# Phase 2: Audit log present on write
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"demo@example.com","password":"Demo1234!"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")" \
  -H "Content-Type: application/json" \
  -d '{"name":"Verify Audit"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
docker compose logs --tail=5 api | jq 'select(.action=="PROJECT_CREATED")'
# Expected: log line with user_id and resource_id

# Phase 3: Bandit passes
cd backend && bandit -r app/ -c pyproject.toml -ll && echo "bandit: PASS"
```

---

## Checkpoint

- [ ] Security headers present on every response (8 headers verified: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, CSP, Cache-Control, Permissions-Policy)
- [ ] Oversized request returns 413 (`Content-Length: 2000000`)
- [ ] `POST /auth/logout` returns 204; same token then returns 401
- [ ] `DELETE /auth/users/me` returns 204; login with same email returns 401
- [ ] Audit log emitted on project creation — includes `user_id` and `resource_id`
- [ ] Soft-deleted user visible in DB with `deleted_at` set
- [ ] Bandit passes locally with no unacknowledged findings
- [ ] Dependabot PR reviewed (if available) or config verified in `.github/dependabot.yml`
- [ ] `.github/CODEOWNERS` committed with security-sensitive paths (middleware, auth router, alembic, workflows) — Phase 4a
- [ ] `GET /.well-known/security.txt` returns `Contact:` and `Policy:` fields — Phase 4b
- [ ] `pytest tests/test_governance.py` passes — all governance controls verified automatically (security headers, body limit, input constraints, password policy, 10 audit events in `test_governance.py` + `COMMENT_CREATED` in `test_tasks_integration.py`, rate limiting, SECRET_KEY validator)
- [ ] ADRs 0003, 0004, and 0005 read and understood — be prepared to explain the JTI revocation trade-off in a code review
- [ ] Commit: `feat(security): enterprise governance — headers, audit logging, token revocation, GDPR, CODEOWNERS, security.txt`
