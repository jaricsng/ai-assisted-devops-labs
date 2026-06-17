# Runbook — HighRejectionRate

**Alert:** HighRejectionRate  
**Severity:** Warning (P3 by default; escalate to P2 if IPs are new/unexpected)  
**Trigger:** `sum(rate(http_server_duration_milliseconds_count{http_status_code="429"}[1m])) > 50`

---

## Triage

1. Confirm alert is real (not a pen-test run):
   ```bash
   docker compose logs api --since=5m | grep '"status_code":429' | head -20
   ```

2. Identify the source IP (if X-Forwarded-For is set by your reverse proxy):
   ```bash
   docker compose logs api --since=5m | grep '"status_code":429' \
     | python3 -c "import sys,json; [print(json.loads(l).get('client_host','?')) for l in sys.stdin if l.strip()]" \
     | sort | uniq -c | sort -rn | head
   ```

3. Determine if this is a scheduled test run:
   - Is a pen test running? (`./pen-tests/manual-checks.sh` fires 10+ login attempts)
   - Is an E2E test running? (`npx playwright test`)

4. Check the audit log for successful logins during the burst:
   ```bash
   docker compose logs api --since=10m | grep '"action":"LOGIN_SUCCESS"' | wc -l
   ```
   If > 5 successes during the burst window: treat as potential credential stuffing with partial success.

---

## Remediation

### If a pen test exhausted the rate-limit bucket:
```bash
docker compose restart api   # clears the in-memory bucket
```
Then re-run E2E tests.

### If this is a real attack:

1. Block the IP at the network/proxy level (WAF, nginx `deny` directive, cloud firewall rule)

2. Check if any accounts were successfully compromised during the burst:
   ```bash
   docker compose logs api --since=60m | grep '"action":"LOGIN_SUCCESS"'
   ```

3. If accounts were compromised: force-expire all tokens by restarting the API (clears in-memory JTI set):
   ```bash
   docker compose restart api
   ```

4. Notify affected users to change their passwords and check for unauthorised activity.

---

## Post-incident

Document the source IP, volume, and whether any logins succeeded.  
Write a brief post-mortem even for P3 incidents — the pattern may recur.

If this repeats, consider:
- Adding IP-based blocking in a WAF or nginx upstream
- Adding CAPTCHA to the login endpoint
- Migrating the rate-limiter bucket to Redis for persistence across restarts (see ADR 0006)

---

## Notes on the current rate limiter

The `RateLimitMiddleware` uses an in-memory sliding-window deque keyed by client IP.
Limitations:
- Resets on API restart — see the pen-test rate note in CLAUDE.md
- Does not share state across multiple API replicas
- Can be evaded by rotating across 100+ IPs (distributed attack)

Production mitigation: Redis-backed rate limiter with distributed state. Tracked in `docs/adr/0007-rate-limiting.md`.
