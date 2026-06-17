# Penetration Test Report — Task Manager API

**Application:** Task Manager API  
**Target:** http://localhost:8000  
**Date:** 2026-06-15 (re-verified)  
**Tester:** Lab Student (authorized owner)  
**Tools:** `pen-tests/manual-checks.sh`, OWASP ZAP baseline scan  
**Scope:** All endpoints on `http://localhost:8000`; frontend not in scope for API pen test  

---

## Executive Summary

A penetration test was conducted against the Task Manager API running on localhost. Six OWASP Top 10 categories were tested plus Module 14 enterprise governance controls, totalling 38 automated checks. The API passed all checks after two findings were remediated: weak password acceptance (FINDING-001) and missing rate limiting (FINDING-002). No critical or high vulnerabilities were found in the final run.

**Overall Risk Rating: LOW** (all medium findings remediated)

---

## Methodology

1. **Recon** — reviewed Swagger UI at `/docs`; identified 14 endpoints across auth, projects, tasks, and comments
2. **Automated scan** — ran `./pen-tests/manual-checks.sh http://localhost:8000`
3. **OWASP ZAP baseline** — ran `./pen-tests/zap-scan.sh http://localhost:8000`
4. **Manual verification** — traced flagged code paths in the source

---

## Findings

### FINDING-001: Weak passwords accepted at registration

| Field | Value |
|-------|-------|
| **OWASP Category** | A07 — Identification and Authentication Failures |
| **Severity** | Medium |
| **CVSS 3.1 Score** | 5.3 (Medium) — AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N |
| **Status** | **Fixed** |

**Evidence:**  
Request: `POST /auth/register` with `"password": "abc"`  
Response before fix: `HTTP 201 Created` — weak password accepted  
Response after fix: `HTTP 422 Unprocessable Entity`

**Root cause:**  
`backend/app/schemas/user.py` — `UserCreate.password` field had no validators.

**Fix applied:**  
Added a `@field_validator("password")` enforcing minimum 8 characters, one uppercase letter, and one digit. Verified: `./pen-tests/manual-checks.sh` now reports PASS on weak password checks.

**Code change:** `backend/app/schemas/user.py:11-20`

---

### FINDING-002: No rate limiting on /auth/login

| Field | Value |
|-------|-------|
| **OWASP Category** | A04 — Insecure Design |
| **Severity** | Medium |
| **CVSS 3.1 Score** | 5.3 (Medium) — AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N |
| **Status** | **Fixed** — `RateLimitMiddleware` (10 req/60 s per IP on `/auth/login`) |

**Evidence:**  
11 consecutive failed login attempts; the 11th triggered `HTTP 429` (max_requests=10, window_seconds=60 per IP).

**Fix applied:**  
`RateLimitMiddleware` added to the middleware stack in `backend/app/main.py` with `max_requests=10, window_seconds=60` targeting `/auth/login`. The response includes a `Retry-After` header.

---

### FINDING-003 (Informational): Server header discloses uvicorn

| Field | Value |
|-------|-------|
| **OWASP Category** | A05 — Security Misconfiguration |
| **Severity** | Informational |
| **CVSS 3.1 Score** | 0.0 (None) |
| **Status** | Accepted risk |

**Evidence:**  
`curl -sI http://localhost:8000/health | grep -i server`  
Response: `server: uvicorn`

**Analysis:**  
Disclosing the server software version helps attackers target known vulnerabilities. In production, a reverse proxy (nginx) in front of uvicorn would suppress this header. Acceptable for the lab environment; document and suppress before production deployment.

---

## Checks Passed

### OWASP A01–A07

| Check | Result |
|-------|--------|
| A01 — IDOR: User B reads User A's project | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B deletes User A's project | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B lists User A's tasks | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B reads User A's task | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B modifies User A's task | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B deletes User A's task | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B lists comments on User A's task | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B adds comment to User A's task | ✅ PASS (HTTP 404) |
| A01 — Unauthenticated access to /projects | ✅ PASS (HTTP 401) |
| A02 — JWT alg:none attack | ✅ PASS (HTTP 401) |
| A02 — Tampered JWT signature | ✅ PASS (HTTP 401) |
| A03 — SQL injection in task title | ✅ PASS (HTTP 201, payload stored as text) |
| A03 — XSS payload in project name | ✅ PASS (HTTP 201, JSON API not vulnerable) |
| A04 — Status transition bypass (TODO→DONE) | ✅ PASS (HTTP 422) |
| A04 — Terminal state bypass (CANCELLED→IN_PROGRESS) | ✅ PASS (HTTP 422) |
| A04 — Rate limiting on /auth/login | ✅ PASS (HTTP 429 on 11th attempt; max_requests=10, window_seconds=60) |
| A04 — User enumeration via login response | ✅ PASS (identical error messages) |
| A05 — CORS: wildcard or arbitrary origin reflected | ✅ PASS (origin not reflected) |
| A05 — Server header discloses technology | ✅ PASS (no framework version exposed) |
| A07 — Weak password "123" accepted | ✅ PASS after fix (HTTP 422) |
| A07 — Empty password accepted | ✅ PASS (HTTP 422) |

### Module 14 — Enterprise Governance Controls

| Check | Result |
|-------|--------|
| Security header X-Content-Type-Options | ✅ PASS |
| Security header X-XSS-Protection | ✅ PASS |
| Security header X-Frame-Options | ✅ PASS |
| Security header Strict-Transport-Security (HSTS) | ✅ PASS |
| Security header Content-Security-Policy | ✅ PASS |
| Security header Referrer-Policy | ✅ PASS |
| Security header Cache-Control: no-store | ✅ PASS |
| Security header Permissions-Policy | ✅ PASS |
| Responsible disclosure GET /.well-known/security.txt | ✅ PASS (Contact + Expires fields present, RFC 9116) |
| Readiness probe GET /ready | ✅ PASS (HTTP 200) |
| Logout POST /auth/logout | ✅ PASS (HTTP 204) |
| Revoked token rejected after logout | ✅ PASS (HTTP 401) |
| GDPR deletion DELETE /auth/users/me | ✅ PASS (HTTP 204) |
| Soft-deleted user's token rejected | ✅ PASS (HTTP 401) |
| Body size limit: Content-Length > 1 MiB | ✅ PASS (HTTP 413) |
| Input validation: project name > 255 chars | ✅ PASS (HTTP 422) |
| Observability: GET /metrics returns 200 | ✅ PASS |

**Manual checks total: 38 PASS, 0 FAIL**

---

### OWASP ZAP Baseline Scan (2026-06-15)

**Scan:** `./pen-tests/zap-scan.sh http://localhost:8000`  
**Result:** 66 passive rules passed · 0 failed · 0 warnings

| Alert | Risk | Instances | Assessment |
|-------|------|-----------|------------|
| Storable and Cacheable Content | Informational (Medium) | 4 | Public endpoints (`/health`, `/docs`, `/ready`, `/openapi.json`) — no user data; caching is acceptable |

No HIGH or MEDIUM ZAP alerts. The single informational finding is an accepted risk.

---

## Remediation Summary

| Priority | Finding | Action | Status |
|----------|---------|--------|--------|
| Medium | FINDING-001: Weak passwords | Added password strength validator | Fixed |
| Medium | FINDING-002: No rate limiting | Added `RateLimitMiddleware` (10/60 s) | Fixed |
| Info | FINDING-003: Server header | Use nginx reverse proxy in production | Accepted |
| Info | ZAP: Cacheable public endpoints | Public endpoints only; no user data | Accepted |
