# ADR 0004 — Security Controls: JWT, bcrypt, Token Revocation, CORS

**Date:** 2026-06-14
**Status:** Accepted

## Context

The Task Manager API must authenticate users and protect resources. We need to choose a token format, a password hashing scheme, a session revocation strategy, and a CORS policy. All decisions must be implementable without external infrastructure dependencies in the local dev environment.

## Decisions

### 1. JWT HS256 for bearer tokens

We use JSON Web Tokens (JWTs) signed with HMAC-SHA256 using a server-side `SECRET_KEY`.

**Why not RS256?** RS256 requires a key pair and a JWKS endpoint. For a single-instance application, the additional complexity provides no security benefit — the asymmetric key advantage matters only when third parties need to verify tokens without the private key.

**Why not opaque tokens + session store?** Opaque tokens require a database lookup on every request. JWTs are self-contained and stateless, which simplifies the architecture and matches the lab's learning objectives around the service layer.

**Constraint:** JWT HS256 is symmetric — anyone with the `SECRET_KEY` can forge tokens. The key must never be committed to source control and must be rotated if compromised.

### 2. bcrypt for password hashing

All passwords are hashed with bcrypt at cost factor 12 before storage. Plaintext passwords are never logged or stored.

**Why bcrypt over Argon2?** bcrypt is battle-tested and universally available in Python via the `bcrypt` library. Argon2 is technically superior for future deployments but adds library complexity without meaningfully changing the security posture for this lab.

**Cost factor 12:** Provides adequate resistance to offline dictionary attacks on modern hardware (~0.3 s per hash). Increase to 13–14 for production deployments with stricter requirements.

### 3. JTI-based token revocation (in-memory)

Each JWT includes a `jti` (JWT ID) claim — a UUID unique to that token issuance. On logout, the JTI is added to an in-memory set (`_revoked_jtis: set[str]`) in the auth service. The `current_user` dependency checks `is_revoked(jti)` before allowing access.

**Trade-off — in-memory vs. Redis:**

| | In-memory | Redis |
|--|-----------|-------|
| Infrastructure | None — works in single process | Requires Redis instance |
| Multi-instance | ❌ Revocation is per-process only | ✅ Shared across all replicas |
| TTL management | ❌ Revoked set grows until restart | ✅ Entries expire automatically |
| Lab complexity | ✅ Simple, no extra service | — |

**Decision:** In-memory for the lab environment. Production deployments with multiple API replicas must replace `_revoked_jtis` with a Redis `SET` using `EXPIRE` keyed to the token's remaining TTL.

### 4. Environment-aware CORS

CORS origins are configured via the `CORS_ORIGINS` environment variable (default: `http://localhost:5173`). The API rejects cross-origin requests from unlisted origins.

**Why not `allow_origins=["*"]`?** A wildcard CORS policy allows any origin to make credentialed requests, defeating the browser same-origin policy as a defence-in-depth layer.

**Production:** Set `CORS_ORIGINS` to the deployed frontend URL. Never use `*` in production with `allow_credentials=True`.

### 5. HTTP security headers (defence-in-depth)

All responses include seven security headers applied by `SecurityHeadersMiddleware` (a `BaseHTTPMiddleware` subclass registered as the outermost middleware in the stack):

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Blocks clickjacking in iframes |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter for older browsers |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS for 1 year |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Blocks inline scripts and framing |
| `Cache-Control` | `no-store` | Prevents sensitive API responses from being stored in browser or proxy caches |

**Why middleware, not per-route?** Middleware applies headers unconditionally to every response — including FastAPI's own 422 validation errors and 401 auth failures — with a single point of change.

**Accepted trade-off:** The strict CSP (`default-src 'none'`) blocks the Swagger UI's inline scripts. In production the `/docs` path would be disabled or have a relaxed per-path CSP.

### 6. Request body size limit

`MaxBodySizeMiddleware` rejects requests with `Content-Length` greater than 1 MiB (1,048,576 bytes) before reading the body, returning HTTP 413. All request schemas also enforce field-level length constraints via Pydantic `StringConstraints`:
- Project/task name: max 255 characters
- Project/task description: max 2,000 characters
- Comment body: max 5,000 characters

**Why:** Unbounded request bodies allow a low-rate denial-of-service attack via large payloads even without authentication.

## Consequences

- Single-process token revocation is a known limitation; operators scaling to multiple replicas must migrate to Redis before go-live
- bcrypt cost factor 12 adds ~0.3 s to every login — acceptable UX; may need tuning at high throughput
- CORS must be updated when deploying to a new frontend domain — operators must set `CORS_ORIGINS` in the environment
- Password policy (8+ chars, uppercase, digit) is enforced in `UserCreate` schema and documented in the user guide
- The strict CSP blocks Swagger UI inline scripts — documented as accepted risk; `/docs` requires CSP relaxation in production if Swagger access is required
- Middleware stack order (outermost → innermost): SecurityHeaders → CORS → MaxBodySize → RateLimit → RequestLogging → Metrics — oversized requests are rejected before any body bytes are read
