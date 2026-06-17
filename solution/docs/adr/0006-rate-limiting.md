# ADR 0006 — Rate Limiting Strategy for Login Endpoint

**Date:** 2026-06-15
**Status:** Accepted

## Context

The `/auth/login` endpoint accepts a username and password and returns a JWT. Without any rate limiting, an attacker can attempt thousands of password combinations per minute — a credential-stuffing or brute-force attack that is invisible to the application until a breach is detected.

The OWASP Top 10 (A04 — Insecure Design) flags the absence of login rate limiting as a design weakness. The Module 12 pen test (`pen-tests/manual-checks.sh`) explicitly tests for it: it fires 20 rapid login attempts and expects a 429 response — exceeding the configured `max_requests=10` limit.

## Options Considered

### Option A — `slowapi` (per-route decorator)

`slowapi` is a popular third-party rate-limiting library for FastAPI that uses a `@limiter.limit("5/minute")` decorator on the route function:

```python
@router.post("/auth/login")
@limiter.limit("5/minute")
async def login(...):
```

**Problem:** This couples rate-limiting configuration to the router layer, not the middleware layer. It also requires adding a `request: Request` parameter to every decorated route and wires Redis as the default backend.

### Option B — Custom `RateLimitMiddleware` (sliding-window, in-memory)

A `BaseHTTPMiddleware` subclass that:
1. Intercepts only `POST /auth/login` requests
2. Maintains a `defaultdict(deque)` keyed by client IP address
3. Drops timestamps older than `window_seconds` on each request
4. Returns HTTP 429 with a `Retry-After` header if `len(deque) >= max_requests`

### Option C — Redis-backed rate limiter

Use Redis `INCR` + `EXPIRE` for a distributed token bucket that survives restarts and works across multiple API replicas.

## Decision

**Option B — custom in-memory middleware** for the lab environment.

The middleware lives at `backend/app/middleware/rate_limit.py` and is registered between `MaxBodySizeMiddleware` and `RequestLoggingMiddleware` in `main.py`. The default class parameters are `max_requests=5, window_seconds=60`; `main.py` overrides these to `max_requests=10` for the lab (the pen test fires 10 requests).

## Why Not Option A (slowapi)?

Rate limiting is a cross-cutting concern — it belongs in the middleware layer, not the router layer. Applying it as a decorator means it only activates after FastAPI has parsed the request body and matched the route; middleware can reject the request earlier. More importantly, coupling the rate-limit policy to the router violates the separation of concerns that the layered architecture enforces everywhere else.

## Why Not Option C (Redis)?

Option C is the correct choice for a multi-instance production deployment — the in-memory bucket is per-process and does not share across replicas. However, it introduces an infrastructure dependency (Redis) that is out of scope for the lab's local dev environment.

The trade-off is explicitly documented in ADR 0004 (JTI revocation faces the same in-memory vs. Redis choice) and in the operator runbook.

## Sliding-Window Algorithm

```
On each POST /auth/login:
  1. Extract client IP from X-Forwarded-For (first value) or REMOTE_ADDR
  2. bucket = deques[ip]
  3. now = time.monotonic()
  4. Drop timestamps where now - ts > window_seconds
  5. If len(bucket) >= max_requests:
       return 429 with Retry-After: window_seconds
  6. Append now to bucket
  7. Forward request
```

The deque never grows beyond `max_requests` entries per IP because excess requests are rejected at step 5. Memory footprint is bounded.

## Consequences

**Positive:**
- Brute-force and credential-stuffing attacks against `/auth/login` are rate-limited per source IP
- No infrastructure dependency — works in the single-Docker-container local dev setup
- `reset_for_testing()` method allows test isolation without restarting the process
- 429 response is returned before any database query or bcrypt comparison executes

**Negative:**
- In-memory state is lost on process restart — an attacker who triggers a restart (e.g., via OOM) resets their bucket
- Does not share state across API replicas — production deployments must replace the in-memory store with Redis
- IP-based limiting can be bypassed via IP rotation or shared NAT addresses (e.g., an office behind a single egress IP)

**Operational note:** The pen test script fires 20 login attempts in rapid succession, which exhausts the `max_requests=10` bucket. Running `docker compose restart api` between the pen test and the E2E test suite resets the in-memory bucket so E2E login tests are not blocked by a pre-filled bucket.

## Future Work

For production multi-replica deployments:
1. Replace `defaultdict(deque)` with `Redis.incr()` + `expire()` per IP key
2. Consider `X-Forwarded-For` spoofing — require a trusted proxy to set the header
3. Apply rate limiting to other write endpoints (`POST /projects`, `POST /tasks`) to prevent data-flood attacks
