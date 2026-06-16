# Runbook — HighRejectionRate

**Alert:** HighRejectionRate  
**Severity:** Warning (P3 by default; escalate to P2 if IPs are new/unexpected)  
**Trigger:** `sum(rate(http_server_duration_milliseconds_count{http_status_code="429"}[1m])) > 50`  
**On-call channel:** #task-manager-oncall

---

## 1. Triage

1. Confirm alert is real (not a pen-test run):
   ```bash
   docker compose logs api --since=5m | grep '"status_code":429' | head -20
   ```

2. Identify the source IP (from `X-Forwarded-For` if set by your reverse proxy):
   ```bash
   docker compose logs api --since=5m | grep '"status_code":429' \
     | python3 -c "import sys,json; [print(json.loads(l).get('client_host','?')) for l in sys.stdin if l.strip()]" \
     | sort | uniq -c | sort -rn | head
   ```

3. Determine if this is a scheduled test run:
   - Is a pen test running? (`./pen-tests/manual-checks.sh` fires 20+ login attempts, triggering 429)
   - Is an E2E test running? (`npx playwright test`)

4. Check the audit log for successful logins during the burst:
   ```bash
   docker compose logs api --since=10m | grep '"action":"LOGIN_SUCCESS"' | wc -l
   ```
   If > 5 successes during the burst window: treat as potential credential stuffing with partial success — escalate to P2.

---

## 2. Identify the Rejection Type (non-429 spikes)

If the alert also shows elevated counts of other 4xx codes:

```bash
# Distribution of 4xx status codes in the last 15 minutes
docker compose logs api --since 15m | python3 -c "
import sys, json, collections
codes = collections.Counter()
for line in sys.stdin:
    try:
        e = json.loads(line)
        sc = e.get('status_code')
        if sc and 400 <= sc < 500:
            codes[sc] += 1
    except: pass
for code, count in codes.most_common():
    print(f'  HTTP {code}: {count}')
"
```

| Dominant code | Likely cause | Go to |
|--------------|-------------|-------|
| 401 | Expired/revoked tokens; client-side auth bug | §3 |
| 422 | API client sending invalid request bodies | §4 |
| 429 | Rate limit triggered (attack or misconfigured client) | §5 |
| 413 | Client sending oversized payloads | §6 |
| 404 | Stale client URLs after a deployment | §7 |

---

## 3. Spike in 401s — Token Issues

```bash
# Check if this started after a deployment that rotated SECRET_KEY
docker compose logs api --since 30m | grep '"event": "api_started"'

# If SECRET_KEY was rotated, all existing tokens are invalidated — users must re-login.
# This is expected behaviour; inform users via status page.

# If SECRET_KEY was NOT rotated, check for clock drift (JWT exp validation)
date && docker compose exec api date
# Clock skew > 5 min will cause exp check failures
```

---

## 4. Spike in 422s — Validation Errors

```bash
# Find which path is generating 422s
docker compose logs api --since 15m | python3 -c "
import sys, json, collections
paths = collections.Counter()
for line in sys.stdin:
    try:
        e = json.loads(line)
        if e.get('status_code') == 422:
            paths[e.get('path', 'unknown')] += 1
    except: pass
for path, count in paths.most_common(10):
    print(f'  {path}: {count}')
"
```

Likely causes: frontend deployed with new field names that don't match the current API schema, or a mobile client on an old version. Check the OpenAPI spec at `docs/api/openapi.yaml` against what the client is sending.

---

## 5. Spike in 429s — Rate Limiting

Current rate limit config: 10 requests / 60 seconds per IP on `/auth/login` (`RateLimitMiddleware`).

### If a pen test exhausted the rate-limit bucket:
```bash
docker compose restart api   # clears the in-memory bucket
```
Then re-run E2E tests.

### If a single IP:
Likely a bot or stuck retry loop. Block at the ingress/WAF level.

### If many IPs:
Possible DDoS — escalate to security team.

### If internal IPs:
A background job or integration is misconfigured — fix the retry backoff.

---

## 6. Spike in 413s — Oversized Payloads

Current limit: 1 MB (`MaxBodySizeMiddleware`). If legitimate use cases exceed this:

1. Identify the endpoint and payload type from logs
2. If file upload was added, the limit may need raising — update `MAX_BODY_SIZE` in `middleware/body_limit.py` and redeploy
3. If it's an attack, the 413 rejections are working as intended — no action needed

---

## 7. Spike in 404s — Stale URLs

Common after a deployment that renames or removes endpoints. Check the API changelog and inform affected clients to update.

---

## 8. Post-Incident

Document the source IP, volume, and whether any logins succeeded.  
Write a brief post-mortem even for P3 incidents — the pattern may recur.

If this repeats, consider:
- Adding IP-based blocking in a WAF or nginx upstream
- Adding CAPTCHA to the login endpoint
- Migrating the rate-limiter bucket to Redis for persistence across restarts (see ADR 0007)

---

## Notes on the current rate limiter

The `RateLimitMiddleware` uses an in-memory sliding-window deque keyed by client IP.
Limitations:
- Resets on API restart — see the pen-test rate note in CLAUDE.md
- Does not share state across multiple API replicas
- Can be evaded by rotating across 100+ IPs (distributed attack)

Production mitigation: Redis-backed rate limiter with distributed state. Tracked in `docs/adr/0007-rate-limiting.md`.
