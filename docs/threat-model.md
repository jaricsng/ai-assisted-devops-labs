# Threat Model — Task Manager API

**Method:** STRIDE  
**Scope:** Task Manager three-tier application (React frontend / FastAPI backend / PostgreSQL)  
**Date:** 2026-06-16  
**Author:** Security review via AI-Assisted DevOps lab

---

## 1. System Overview

```
┌─────────────────┐   HTTPS/TLS   ┌──────────────────┐   asyncpg   ┌──────────────┐
│  React Frontend │ ────────────▶ │  FastAPI Backend  │ ──────────▶ │  PostgreSQL   │
│  (Vite, :5173)  │               │  (uvicorn, :8000) │             │  (:5432)      │
└─────────────────┘               └──────────────────┘             └──────────────┘
        │                                  │
        │  Browser/localStorage            │  OTLP gRPC
        │  JWT (access_token)              ▼
        │                         ┌──────────────────┐
        │                         │  Jaeger / OTel   │
        │                         │  Prometheus       │
        │                         └──────────────────┘
```

**Trust boundaries:**
- Browser ↔ API: public internet; auth via JWT Bearer token
- API ↔ DB: internal network; auth via connection string credentials
- API ↔ Observability: internal network; unauthenticated (Jaeger, Prometheus)

**Assets:**
- User PII (email, full name, hashed password)
- Task and project data (owner-scoped)
- JWT signing key (`SECRET_KEY`)
- Database credentials (`DATABASE_URL`)

---

## 2. STRIDE Threat Register

| ID | Category | Component | Threat | Likelihood | Impact | Risk | Mitigation | Status |
|----|----------|-----------|--------|-----------|--------|------|-----------|--------|
| T-01 | **S**poofing | Auth | Attacker uses `alg:none` JWT to bypass signature verification | Medium | Critical | High | `jose.decode()` called with `algorithms=["HS256"]`; token with any other alg rejected with 401 | Mitigated |
| T-02 | **S**poofing | Auth | Brute-force login against known email | High | High | High | `RateLimitMiddleware` caps `/auth/login` at 10 req/60 s per IP; returns 429 with `Retry-After` | Mitigated |
| T-03 | **S**poofing | Auth | Session fixation via replayed JWT after logout | Medium | High | High | `jti` UUID claim; `is_revoked()` checks in-memory set on every request; logout adds jti to set | Mitigated |
| T-04 | **T**ampering | Auth | Attacker forges JWT claims (e.g. `sub`) by changing payload without re-signing | High | Critical | Critical | Signature verified with `HS256` + `SECRET_KEY`; tampered token returns 401 | Mitigated |
| T-05 | **T**ampering | Tasks | Attacker patches another user's task via IDOR | High | High | High | All task/project queries filter `owner_id = current_user.id`; returns 404 (not 403) to avoid leaking existence | Mitigated |
| T-06 | **T**ampering | Tasks | Attacker bypasses status machine by sending arbitrary `status` transitions | Medium | Medium | Medium | `validate_status_transition()` in `task_service.py` enforces TODO→IN_PROGRESS→IN_REVIEW→DONE; invalid → 422 | Mitigated |
| T-07 | **T**ampering | Input | SQL injection via task title, project name, or comment body | Medium | Critical | High | All DB access via SQLAlchemy ORM with parameterised queries; no raw SQL strings | Mitigated |
| T-08 | **T**ampering | Input | XSS via stored project/task name rendered in React | Medium | High | High | React escapes content by default; Content-Security-Policy header set to `default-src 'self'` | Mitigated |
| T-09 | **R**epudiation | Audit | Write operations (create/update/delete) lack audit trail | Low | High | Medium | Every write emits structlog `audit` event with `action`, `resource`, `resource_id`, `user_id` | Mitigated |
| T-10 | **R**epudiation | Observability | Log lines lack request correlation | Low | Medium | Low | `RequestLoggingMiddleware` binds `request_id` (UUID v4) via contextvars to every log line in a request | Mitigated |
| T-11 | **I**nformation Disclosure | Auth | User enumeration via distinct error messages for wrong email vs wrong password | High | Medium | Medium | Both cases return identical `"Invalid credentials."` message with identical 401 status | Mitigated |
| T-12 | **I**nformation Disclosure | Auth | Registration response exposes `hashed_password` field | Low | High | Medium | `UserResponse` Pydantic schema excludes `hashed_password`; tested in `test_auth_integration.py` | Mitigated |
| T-13 | **I**nformation Disclosure | Error handling | Unhandled exceptions leak stack traces to clients | Medium | High | High | Global `unhandled_exception_handler` catches all `Exception` and returns generic 500 JSON | Mitigated |
| T-14 | **I**nformation Disclosure | Headers | Server fingerprinting via `Server` / `X-Powered-By` headers | Medium | Low | Low | `SecurityHeadersMiddleware` removes / overrides fingerprinting headers | Mitigated |
| T-15 | **I**nformation Disclosure | Secrets | `SECRET_KEY` / `DATABASE_URL` committed to source control | Low | Critical | High | `.env` in `.gitignore`; `detect-secrets` pre-commit hook with `.secrets.baseline`; example values in `.env.example` only | Mitigated |
| T-16 | **D**enial of Service | Input | Oversized request body causes memory exhaustion | Medium | High | High | `MaxBodySizeMiddleware` rejects requests > 1 MB with 413 | Mitigated |
| T-17 | **D**enial of Service | Input | Excessively long field values cause DB slow queries or index bloat | Medium | Medium | Medium | `max_length` constraints on all Pydantic schemas (e.g. title ≤ 200 chars); 422 on violation | Mitigated |
| T-18 | **D**enial of Service | Auth | Login endpoint flooded by automated credential stuffing | High | High | High | Rate limit (T-02) + bcrypt cost factor slows enumeration | Mitigated |
| T-19 | **E**levation of Privilege | Auth | Regular user accesses another user's projects or tasks | High | High | Critical | Owner-scoped queries (T-05); no admin-bypass paths exposed | Mitigated |
| T-20 | **E**levation of Privilege | CI/CD | Malicious package in `requirements.txt` gains code execution in CI | Medium | Critical | High | `pip-audit` runs in every CI pipeline job; SLSA provenance generation planned | Partial |
| T-21 | **E**levation of Privilege | Observability | `/metrics` endpoint exposes internal counters without auth | Low | Medium | Low | `/metrics` only mounted when `OTEL_ENABLED=true`; in production, mount behind internal-only ingress rule | Accepted |
| T-22 | **S**poofing | CORS | Cross-origin request forged by malicious site | Medium | High | High | `CORSMiddleware` configured with explicit `allow_origins`; credentials flag set | Mitigated |
| T-23 | **T**ampering | Supply chain | Compromised npm package in frontend build | Medium | High | High | `npm audit` in CI; lock file committed; dependency review recommended | Partial |

---

## 3. Residual Risks

| ID | Risk | Accepted? | Owner | Notes |
|----|------|-----------|-------|-------|
| T-20 | Supply chain via compromised PyPI package | Partial | Platform team | SLSA provenance generation (Task 7) will add build attestation |
| T-21 | `/metrics` accessible without auth | Accepted | Ops | Mitigated at infra layer (network policy); low data sensitivity |
| T-23 | npm supply chain | Partial | Frontend team | `npm audit` catches known CVEs; Dependabot alerts recommended |

---

## 4. Controls Summary

| Control | Where implemented |
|---------|------------------|
| JWT HS256 signature verification | `backend/app/services/auth_service.py` |
| JTI revocation on logout | `backend/app/services/auth_service.py::is_revoked()` |
| Rate limiting (10/60 s) on `/auth/login` | `backend/app/middleware/rate_limit.py` |
| Owner-scoped SQL queries | `backend/app/repositories/` (all queries) |
| Status machine enforcement | `backend/app/services/task_service.py::validate_status_transition()` |
| SQL injection prevention (ORM) | `backend/app/repositories/` (SQLAlchemy ORM only) |
| XSS prevention (CSP header) | `backend/app/middleware/security_headers.py` |
| Request body size limit (1 MB) | `backend/app/middleware/body_limit.py` |
| Input length validation | `backend/app/schemas/` (Pydantic `max_length`) |
| Audit logging | All service write methods (structlog `audit` event) |
| Secret scanning | `.pre-commit-config.yaml` (detect-secrets v1.5.0) |
| Dependency CVE scan | CI pipeline (pip-audit + npm audit) |
| Generic error responses | `backend/app/main.py::unhandled_exception_handler()` |

---

## 5. Out of Scope

- Network-layer controls (TLS termination, WAF, DDoS protection) — assumed to be handled by the platform/ingress layer
- Physical security
- Social engineering / phishing

---

## 6. Review Schedule

This threat model should be reviewed when:
- A new authentication method or identity provider is added
- New external integrations are introduced
- A significant change to the data model (new PII fields) is deployed
- A security incident occurs
