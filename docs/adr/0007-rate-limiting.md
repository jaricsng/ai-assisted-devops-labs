# ADR 0007 — Rate Limiting: Sliding-Window In-Memory Middleware

**Date:** 2026-06-16
**Status:** Accepted

## Context

Brute-force credential stuffing against `/auth/login` is a realistic threat vector — attackers automate thousands of login attempts per second using leaked credential lists. The API must detect and block high-frequency login attempts without requiring external infrastructure in the local dev environment.

Constraints:
- Must work in a single-process local environment (no Redis, no shared state)
- Must not affect normal users (low false-positive rate)
- Must be resettable in tests without restarting the process
- Must respond with the correct HTTP semantics (429 + `Retry-After`)

## Decision

We implement a **custom sliding-window rate limiter** as a `BaseHTTPMiddleware` subclass (`RateLimitMiddleware` in `backend/app/middleware/rate_limit.py`), applied only to `POST /auth/login`.

### Algorithm

Each client IP maintains a `deque[float]` of request timestamps (monotonic clock). On every request:

1. Drop timestamps older than `window_seconds` from the front of the deque
2. If `len(deque) >= max_requests`, return 429 with `Retry-After: N` (seconds until the oldest timestamp expires)
3. Otherwise append the current timestamp and pass the request through

This is a true **sliding window** — it counts requests in the preceding `window_seconds` of real time, not in a fixed bucket. Fixed-bucket counters (e.g., "5 per minute, resetting at :00") can be gamed by two bursts straddling the bucket boundary.

**Default parameters:** 10 requests per 60-second sliding window per IP.

### IP extraction

Client IP is read from `X-Forwarded-For` (first address if multiple) with fallback to `request.client.host`. This correctly handles reverse proxies (nginx, Caddy, cloud load balancers) while retaining the real client IP.

**Warning:** If the API is deployed behind a proxy that does not set `X-Forwarded-For`, all clients appear as the proxy IP and will share a single rate-limit bucket. Production deployments must ensure the ingress proxy forwards the real client IP.

### Scope

The middleware is **path-specific** — only `POST /auth/login` is rate-limited. All other paths pass through immediately. Rate limiting is not applied to `/auth/register` in the current implementation; this is a known gap (a slow registration loop is possible but requires a valid email per attempt, which reduces practical threat from scripted attacks).

### Test isolation

`reset_for_testing()` clears all IP buckets without restarting the process. Test fixtures call this function to prevent state bleed between tests that exercise the rate-limited endpoint.

The following behaviours are verified in `tests/test_governance.py`:
- **X-Forwarded-For extraction:** `test_rate_limit_uses_x_forwarded_for_header` confirms that `_client_ip()` uses the first address from `X-Forwarded-For` as the bucket key rather than `request.client.host`.
- **Sliding-window expiry:** `test_rate_limit_sliding_window_drops_expired_entries` pre-injects a stale timestamp (epoch 0) and confirms the `deque.popleft()` path fires, removing the expired entry before counting.

## Why not `slowapi`?

[`slowapi`](https://github.com/laurents/slowapi) is a popular FastAPI rate limiting library backed by `limits` (Redis or in-memory). It was evaluated and rejected for this lab for two reasons:

1. **Coupling complexity:** slowapi's key functions are decorator-based, which ties rate limiting logic into the router layer. The lab enforces a strict router/service/repository boundary; cross-cutting concerns belong in middleware.
2. **Unnecessary dependency:** The lab's threat model needs only a single protected path (`/auth/login`). A 60-line custom middleware achieves this without pulling in `slowapi`'s dependency chain.

For production systems protecting many endpoints with different limits, `slowapi` + Redis is the correct choice.

## Why not a WAF or API gateway?

WAF/gateway-level rate limiting (AWS WAF, Azure Front Door, Cloudflare) is the correct production control — it operates before traffic reaches the application and scales horizontally automatically. It is not used here because:

- The local dev environment has no WAF
- The lab teaches application-layer security; WAF configuration is an infrastructure concern outside the curriculum scope

Production deployments should add a WAF rate limit **in addition to** (not instead of) the application-layer limiter, following a defence-in-depth approach.

## Trade-offs

| Concern | In-memory (current) | Redis-backed (production) |
|---------|---------------------|--------------------------|
| Infrastructure | None | Redis instance required |
| Multi-instance | ❌ Each process has its own buckets | ✅ Shared counter across replicas |
| Persistence | ❌ Buckets reset on restart | ✅ Survives restarts (with TTL) |
| Lab complexity | ✅ Simple | — |

## Consequences

- A single API replica (local Docker, single ECS task) is fully protected; horizontal scaling without Redis means each replica enforces limits independently — a determined attacker can multiply attempt rate by number of replicas
- **Production requirement:** Replace `_revoked_jtis` set (ADR 0003) and rate-limit buckets with Redis before deploying multiple replicas; document in runbook
- The pen test (`pen-tests/manual-checks.sh`) fires 20 rapid login attempts to verify the 429 response — exceeding the configured `max_requests=10` limit. This exhausts the in-memory bucket; **run `docker compose restart api` to reset state before running E2E tests** after a pen test
- `ENVIRONMENT=test` does not automatically reset rate-limit state — test fixtures that exercise `/auth/login` must call `reset_for_testing()` explicitly to avoid state bleed
- The `Retry-After` header tells compliant clients how long to wait; non-compliant clients (curl scripts, attackers) will ignore it — the bucket still blocks them regardless
