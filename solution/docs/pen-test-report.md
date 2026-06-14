# Penetration Test Report — Task Manager API

**Application:** Task Manager API  
**Target:** http://localhost:8000  
**Date:** 2026-06-14  
**Tester:** Lab Student (authorized owner)  
**Tools:** `pen-tests/manual-checks.sh`, OWASP ZAP baseline scan  
**Scope:** All endpoints on `http://localhost:8000`; frontend not in scope for API pen test  

---

## Executive Summary

A penetration test was conducted against the Task Manager API running on localhost. Six OWASP Top 10 categories were tested. The API passed all automated security checks after one finding was remediated (weak password acceptance). No critical or high vulnerabilities were found in the final run. One medium finding (missing rate limiting on the login endpoint) was accepted as a risk and documented below.

**Overall Risk Rating: LOW** (after remediation of the one fixed finding)

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
| **Status** | **Accepted risk** — documented in this report |

**Evidence:**  
20 consecutive failed login attempts all returned `HTTP 401` with no throttling or lockout.

**Risk accepted because:**  
- This is a development/lab environment, not a production system with real users
- Implementing rate limiting with `slowapi` would require Redis or in-memory state, adding operational complexity outside the lab scope
- The bcrypt password hashing makes brute force computationally expensive even without rate limiting (each check takes ~100ms)

**Mitigation if deployed to production:**  
Add `slowapi` middleware: `@limiter.limit("5/minute")` on the `/auth/login` endpoint. Reference: Module 5, extension exercise.

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

| Check | Result |
|-------|--------|
| A01 — IDOR: User B reads User A's project | ✅ PASS (HTTP 404) |
| A01 — IDOR: User B modifies User A's task | ✅ PASS (HTTP 404) |
| A01 — Unauthenticated access to /projects | ✅ PASS (HTTP 403) |
| A02 — JWT alg:none attack | ✅ PASS (HTTP 401) |
| A02 — Tampered JWT signature | ✅ PASS (HTTP 401) |
| A03 — SQL injection in task title | ✅ PASS (HTTP 201, payload stored as text) |
| A03 — XSS payload in project name | ✅ PASS (HTTP 201, JSON API not vulnerable) |
| A04 — Status transition bypass (TODO→DONE) | ✅ PASS (HTTP 422) |
| A05 — CORS: wildcard or arbitrary origin reflected | ✅ PASS (origin not reflected) |
| A07 — Weak password "123" accepted | ✅ PASS after fix (HTTP 422) |
| A07 — Empty password accepted | ✅ PASS (HTTP 422) |
| A07 — User enumeration via login response | ✅ PASS (identical error messages) |

---

## Remediation Summary

| Priority | Finding | Action | Status |
|----------|---------|--------|--------|
| Medium | FINDING-001: Weak passwords | Added password strength validator | Fixed |
| Medium | FINDING-002: No rate limiting | Accepted risk; document for production | Accepted |
| Info | FINDING-003: Server header | Use nginx reverse proxy in production | Accepted |
