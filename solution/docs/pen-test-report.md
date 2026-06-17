# Penetration Test Report — Task Manager API

**Application:** Task Manager API  
**Target:** http://localhost:8000  
**Date:** 2026-06-14  
**Tester:** Lab Student (authorized owner)  
**Tools:** `pen-tests/manual-checks.sh`, OWASP ZAP baseline scan  
**Scope:** All endpoints on `http://localhost:8000`; frontend not in scope for API pen test  

---

## Executive Summary

A penetration test was conducted against the Task Manager API running on localhost. Six OWASP Top 10 categories were tested using `pen-tests/manual-checks.sh` (38 automated checks). The API passed all checks after two findings were remediated: weak password acceptance and missing rate limiting. No critical or high vulnerabilities were found in the final run.

**Overall Risk Rating: LOW** (after remediation of both findings)

---

## Methodology

1. **Recon** — reviewed Swagger UI at `/docs`; identified 12 endpoints across auth, projects, tasks, and comments
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
| **Status** | **Fixed** |

**Evidence before fix:**  
20 consecutive failed login attempts all returned `HTTP 401` with no throttling or lockout.

**Evidence after fix:**  
`POST /auth/login` returns `HTTP 429 Too Many Requests` with `Retry-After` header on the 11th attempt within a 60-second window. Verified via `pen-tests/manual-checks.sh`.

**Fix applied:**  
`RateLimitMiddleware` added in `backend/app/middleware/rate_limit.py` — sliding-window deque keyed by client IP, configured as `max_requests=10, window_seconds=60`. Wired in `backend/app/main.py`. See ADR 0007 for design rationale and trade-offs (in-memory vs Redis).

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

## Checks Passed (38 total)

| Check | Result |
|-------|--------|
| A01 — IDOR: User B reads User A's project | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B deletes User A's project | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B lists tasks in User A's project | ✅ PASS (HTTP 404) |
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
| A04 — Terminal state CANCELLED is irreversible | ✅ PASS (HTTP 422) |
| A04 — Rate limiting active (429 on 11th attempt) | ✅ PASS after fix (HTTP 429 + Retry-After) |
| A04 — No user enumeration | ✅ PASS (identical error messages) |
| A05 — CORS: wildcard or arbitrary origin reflected | ✅ PASS (origin not reflected) |
| A05 — Server header does not disclose versions | ✅ PASS |
| A07 — Weak password "123" accepted | ✅ PASS after fix (HTTP 422) |
| A07 — Empty password accepted | ✅ PASS (HTTP 422) |
| Module 14 — X-Content-Type-Options present | ✅ PASS |
| Module 14 — X-XSS-Protection present | ✅ PASS |
| Module 14 — X-Frame-Options present | ✅ PASS |
| Module 14 — HSTS present | ✅ PASS |
| Module 14 — Content-Security-Policy present | ✅ PASS |
| Module 14 — Referrer-Policy present | ✅ PASS |
| Module 14 — Cache-Control: no-store present | ✅ PASS |
| Module 14 — Permissions-Policy present | ✅ PASS |
| Module 14 — security.txt returns Contact field (RFC 9116) | ✅ PASS |
| Module 14 — /ready returns 200 | ✅ PASS |
| Module 14 — Logout returns 204 | ✅ PASS |
| Module 14 — Revoked token rejected with 401 | ✅ PASS |
| Module 14 — GDPR deletion returns 204 | ✅ PASS |
| Module 14 — Soft-deleted user's token rejected with 401 | ✅ PASS |
| Module 14 — Body size limit: Content-Length > 1 MiB returns 413 | ✅ PASS |
| Module 14 — Input validation: project name > 255 chars returns 422 | ✅ PASS |
| Module 14 — GET /metrics returns 200 | ✅ PASS |

**Manual checks total: 38 PASS, 0 FAIL**

---

## Remediation Summary

| Priority | Finding | Action | Status |
|----------|---------|--------|--------|
| Medium | FINDING-001: Weak passwords | Added password strength validator | Fixed |
| Medium | FINDING-002: No rate limiting | Added `RateLimitMiddleware` (10 req/60 s) | Fixed |
| Info | FINDING-003: Server header | Use nginx reverse proxy in production | Accepted |
