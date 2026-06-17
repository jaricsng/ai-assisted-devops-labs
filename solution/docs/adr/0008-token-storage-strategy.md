# ADR 0008 — JWT Storage Strategy: localStorage vs. httpOnly Cookie

**Date:** 2026-06-15  
**Status:** Proposed  
**Authors:** Lab Student  
**Context module:** Module 19 — Threat Modeling

---

## Context

JWT access tokens are currently stored in browser `localStorage` (see `frontend/src/App.tsx`).
`localStorage` is accessible to any JavaScript running on the page. If an attacker exploits an XSS
vulnerability in the React frontend, they can steal the token and use it to impersonate the user.

This was identified as threat **T-02 (Partially mitigated)** in `docs/threat-model.md`.

The CSP header (`default-src 'none'`) significantly reduces XSS risk by blocking inline scripts.
However, a compromised npm package in the build could still execute as first-party JavaScript and
access `localStorage`, bypassing the CSP.

This ADR documents the options, the rationale for the current choice, and the production migration path.

---

## Options

### Option A — Keep localStorage (current)

**How it works:** `localStorage.setItem("token", jwt)` on login; `localStorage.getItem("token")`
on every API call.

**Pros:**
- Simple to implement — the current codebase already does this.
- Works with the current stateless JWT architecture.
- No server-side session state required.

**Cons:**
- Accessible to any JavaScript — XSS attack can steal tokens.
- CSP mitigates but does not eliminate the risk (first-party script can still read it).

**Risk:** T-02 (Partially mitigated)

---

### Option B — httpOnly Cookie with CSRF Token

**How it works:** The API sets the JWT as an httpOnly cookie on login. The browser sends the
cookie automatically on every request. A CSRF token (in a separate readable cookie or response
header) is required on state-changing requests to prevent CSRF attacks.

**Pros:**
- Token is inaccessible to JavaScript — XSS cannot steal it.
- Widely used pattern for server-rendered apps.

**Cons:**
- Requires the API to set and clear the cookie (login/logout changes).
- CORS policy must be updated to `allow_credentials=True`.
- Every state-changing request must include a CSRF token header.
- More complex to implement and test.

**FastAPI changes required:**
```python
# In auth router — login response
response.set_cookie(
    "access_token",
    value=token,
    httponly=True,
    secure=True,
    samesite="strict",
    max_age=1800,  # 30 minutes
)

# CORS config
CORSMiddleware(
    allow_origins=[settings.cors_origins],
    allow_credentials=True,  # must be True for cookies to be sent cross-origin
)
```

---

### Option C — In-Memory Storage with httpOnly Refresh Token (Recommended for production)

**How it works:** The short-lived access token (15 minutes) lives only in React component state
— lost on page refresh. A long-lived refresh token (7 days) is stored in an httpOnly cookie.
A `/auth/refresh` endpoint silently issues a new access token using the refresh token.

**Pros:**
- Access token never written to disk — inaccessible to XSS and persistent JS attacks.
- Refresh token in httpOnly cookie is XSS-proof.
- Industry gold standard for SPAs (used by Auth0, Okta).

**Cons:**
- Requires a `/auth/refresh` endpoint on the API.
- React app must handle token refresh on page load and on expiry.
- More complex; requires careful handling of the refresh-token rotation flow.
- Silent refresh can fail if the refresh token expires — user is logged out.

---

## Decision

**Keep `localStorage` for the lab (Option A).** The CSP header blocks the primary XSS attack
vector (inline scripts and external scripts). Moving to Option B or C would require significant
changes to both the API and the React app, which is out of scope for this learning exercise.

This decision is documented in `docs/threat-model.md` as T-02 (Partially mitigated) with
rationale.

**For production:** Option C (in-memory + httpOnly refresh token) is recommended. This decision
is deferred until the application moves out of lab context. The `/auth/refresh` endpoint should
be the first security feature added in a production hardening sprint.

---

## Consequences

**Accepted:**
- The XSS risk is partially mitigated via CSP, not eliminated.
- Any third-party npm package added to the frontend must be carefully vetted — it could steal
  tokens via `localStorage.getItem("token")`.
- Dependabot and `npm audit` (wired in CI) reduce but cannot eliminate this risk.

**Future:**
- Option C implementation would require: `POST /auth/refresh` endpoint in FastAPI,
  `GET /auth/me` for session recovery on page load, refresh-token rotation logic, and
  React state management changes in `App.tsx`.
- Estimated effort: medium (3–5 days for a developer familiar with both tiers).
