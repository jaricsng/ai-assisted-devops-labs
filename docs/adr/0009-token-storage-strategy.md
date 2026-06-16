# ADR 0009 — JWT Token Storage: localStorage with CSP Mitigation

**Date:** 2026-06-16
**Status:** Accepted

## Context

JWTs issued by `/auth/login` must be persisted in the browser so the React SPA can include them as `Authorization: Bearer` headers in subsequent API requests. The storage location determines the XSS attack surface.

This decision was revisited during Module 19 (Threat Modeling) when threat T-02 (token theft via XSS) was formally identified in the STRIDE analysis.

Three options were evaluated:

| Option | Storage | XSS exposure | CSRF exposure |
|--------|---------|-------------|--------------|
| A — `localStorage` | Disk-persistent JS-accessible storage | Full — any JS can read it | None — not sent automatically |
| B — `httpOnly` cookie | Browser-managed, JS-inaccessible | None | Present — sent on all requests |
| C — In-memory + `httpOnly` refresh token | React state (lost on refresh) + cookie | Minimal | Minimal (access token never in cookie) |

## Decision

**Option A — `localStorage`** is used in the current implementation (`frontend/src/App.tsx`).

The primary XSS attack vector (inline scripts, external scripts loaded from other origins) is blocked by the `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` header enforced by `SecurityHeadersMiddleware`. No external script can run on the frontend origin; no inline script executes.

**This decision is accepted for the lab.** It is explicitly tracked as threat T-02 (Partially mitigated) in `docs/threat-model.md`.

**For production: implement Option C.** The `/auth/refresh` endpoint should be the first security feature added in a production hardening sprint. See the production migration path below.

## Rationale

### Why `localStorage` for the lab?

`localStorage` requires zero server-side changes — the API remains purely stateless. The React implementation is simple and already in place. Moving to Option B or C requires:

- Server-side: cookie-setting login/logout responses, a `/auth/refresh` endpoint, CSRF token infrastructure
- Frontend: session recovery on page load (`GET /auth/me`), silent refresh logic before token expiry, CSRF header on every state-changing request

These changes are valuable for production but out of scope for a learning lab focused on DevOps practices.

### Known limitation

A compromised first-party script — e.g., a supply-chain attack on an npm package that is bundled into the frontend — can call `localStorage.getItem("token")` and exfiltrate the token. This bypasses the CSP (which blocks external scripts, not build-time first-party code).

**Mitigations already in place:**
- `npm audit` in CI fails the build on HIGH/CRITICAL vulnerabilities
- Dependabot opens weekly PRs to update npm packages
- Subresource Integrity (SRI) is not applied to locally-bundled assets (not applicable for Vite builds)

The residual risk is accepted and documented in the threat model.

### Production migration path (Option C)

```python
# POST /auth/login — in the auth router
response.set_cookie(
    "refresh_token",
    value=refresh_token,
    httponly=True,
    secure=True,
    samesite="strict",
    max_age=604800,  # 7 days
    path="/auth/refresh",  # scoped to refresh endpoint only
)
# Return the short-lived access token in the response body (stored in React state only)
return {"access_token": access_token, "token_type": "bearer"}
```

Required API additions:
- `POST /auth/refresh` — verifies the httpOnly refresh token cookie, issues a new access token
- `GET /auth/me` — returns the current user from an access token (for session recovery on page load)

Required frontend additions:
- On app load: call `GET /auth/me` to recover session if a refresh token cookie exists
- On 401 response: attempt silent refresh via `POST /auth/refresh` before redirecting to login

## Consequences

- `localStorage` token storage is vulnerable to first-party XSS (supply-chain attack on an npm package); CSP blocks external scripts but not build-time code
- Any new npm dependency added to the frontend must be vetted — it runs as first-party JavaScript with `localStorage` access
- Token expiry (30 minutes) limits the exfiltration damage window
- The threat model (`docs/threat-model.md`) documents T-02 with Likelihood=Medium / Impact=High / Risk=High / Status=Partially mitigated
- The CORS policy (`allow_credentials=True`) is already set — migrating to Option C requires server-side cookie handling but not a CORS policy change
- Option C estimated effort: 3–5 developer-days for a developer familiar with both tiers
