# ADR 0002 — JWT Authentication with python-jose

**Date:** 2026-06-14  
**Status:** Accepted

## Context

The API needs to authenticate users across stateless HTTP requests. The options were:

1. **Session cookies** — server stores session state, browser sends cookie automatically
2. **JWT (JSON Web Tokens)** — server issues signed token, client sends it in `Authorization: Bearer` header
3. **OAuth2 / third-party auth** — delegate to Google, GitHub, etc.

## Decision

We use **JWT with HS256 signing** via `python-jose`. Tokens are issued on `/auth/login` and expire after 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

Key implementation constraints:
- The signing algorithm is **explicitly pinned to `["HS256"]`** in the `jwt.decode()` call. This prevents the `alg:none` attack.
- The `SECRET_KEY` is loaded from the environment via `pydantic-settings`. It is never hardcoded and never committed to git.
- Tokens carry `sub` (user ID), `exp`, and `jti` (JWT ID — added in Module 14) claims. No roles or sensitive data in the payload.
- The `HTTPBearer` security scheme in FastAPI automatically returns 403 if no token is provided, and the `deps.py` dependency returns 401 if the token is invalid, expired, or revoked.

## Consequences

**Positive:**
- Stateless — the API does not need a session store; each request is independently verifiable
- Works naturally with the React SPA (token stored in `localStorage`, sent in every API request)
- The `alg:none` attack is blocked by the explicit algorithm list
- Token expiry limits the damage window if a token is leaked
- JTI-based revocation (Module 14) allows immediate logout and GDPR account deletion

**Negative:**
- `localStorage` storage is vulnerable to XSS — if the frontend is compromised, the token can be stolen. (Mitigation: strict CSP headers; future work: `httpOnly` cookie storage)
- Short token lifetime (30 minutes) means the React app must handle 401 responses and redirect to login
- In-memory JTI revocation set is per-process — does not share across replicas; restart loses all revocations (see ADR 0004 for the Redis trade-off)

**Trade-off not taken:**
Session cookies with CSRF protection would be more secure for a browser application, but require a session store (Redis or DB) and CSRF token handling in the frontend. JWT keeps the API stateless and the implementation simpler for this lab context.

## Module 14 update — JTI revocation

The original decision accepted that tokens could not be revoked before expiry. Module 14 (Enterprise Governance) addressed this:

- Every `create_access_token()` call now includes a `jti` UUID claim unique to that issuance
- `POST /auth/logout` calls `revoke_token(jti)`, adding the JTI to an in-memory `set[str]`
- The `current_user` dependency calls `is_revoked(jti)` and returns 401 if the token has been revoked
- `DELETE /auth/users/me` soft-deletes the account and revokes the current token in one operation

The in-memory store is a known limitation for multi-replica deployments — see ADR 0004 for the full trade-off analysis.
